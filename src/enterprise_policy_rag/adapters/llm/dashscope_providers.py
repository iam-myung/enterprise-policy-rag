"""DashScope 真实 Provider（chat / rerank / conflict），SPEC §5 / §9.3。

把 Qwen/DashScope 的文本生成包装为各 Port 需要的 callable：
- chat_provider: ChatPrompt -> ModelAnswerDTO
- rerank_provider: (question, candidates) -> list[evidence_id]
- conflict_provider: (question, candidates) -> ConflictAssessmentDTO
"""

import json
import os
import re
from typing import Any, cast

from dashscope import Generation

from enterprise_policy_rag.adapters.llm.qwen_chat_model import ChatPrompt
from enterprise_policy_rag.application.ports.models import (
    ConflictAssessmentDTO,
    ConflictReasonCode,
    ModelAnswerDTO,
)
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerStatus


def _api_key() -> str:
    return os.environ.get("DASHSCOPE_API_KEY", "")


def _model(name: str) -> str:
    return os.environ.get(name, "") or "qwen-turbo"


def _call(system: str, user: str, model: str) -> str:
    messages = cast(
        Any,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    resp = cast(
        Any,
        Generation.call(
            model=model,
            api_key=_api_key(),
            messages=messages,
            result_format="message",
        ),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"DashScope 调用失败：{resp.status_code} {resp.message}")
    return str(resp.output.choices[0].message.content)


def _parse_json(content: str) -> dict[str, Any]:
    """从模型输出提取 JSON（容错 markdown 代码块）。"""
    text = content.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return cast(dict[str, Any], json.loads(text))


def chat_provider(prompt: ChatPrompt) -> ModelAnswerDTO:
    """回答生成 provider（SPEC §9.3）：结构化 JSON 输出。"""
    user = (
        f"{prompt.user}\n\n"
        '请只输出 JSON：{"status": "ANSWERED|NO_EVIDENCE|CONFLICT", '
        '"answer": "...", "citation_ids": ["e1"], "conflict_note": null}'
    )
    content = _call(prompt.system, user, _model("CHAT_MODEL"))
    data = _parse_json(content)
    return ModelAnswerDTO(
        status=AnswerStatus(str(data["status"])),
        answer=str(data.get("answer", "")),
        citation_ids=tuple(str(x) for x in data.get("citation_ids", [])),
        conflict_note=data.get("conflict_note"),
    )


def rerank_provider(question: str, candidates: tuple[Evidence, ...]) -> list[str]:
    """重排 provider（SPEC §5.316）：按相关性排序返回 evidence_id 列表。"""
    evidence_lines = "\n".join(
        f"[{e.evidence_id}] {e.title} p{e.page}: {e.quote}" for e in candidates
    )
    user = (
        f"问题：{question}\n候选证据：\n{evidence_lines}\n\n"
        "请按与问题的相关性从高到低，只输出 evidence_id 的 JSON 数组，例如 "
        '["e3", "e1", "e2"]'
    )
    content = _call(
        "你是检索重排器，只输出给定 evidence_id 的排序 JSON 数组。",
        user,
        _model("RERANK_MODEL"),
    )
    data = cast(list[Any], json.loads(_extract_json_array(content)))
    return [str(x) for x in data]


def conflict_provider(
    question: str, candidates: tuple[Evidence, ...]
) -> ConflictAssessmentDTO:
    """冲突判定 provider（SPEC §4.4 / §5.317）。"""
    evidence_lines = "\n".join(
        f"[{e.evidence_id}] {e.title} p{e.page}: {e.quote}" for e in candidates
    )
    user = (
        f"问题：{question}\n候选证据：\n{evidence_lines}\n\n"
        "判断这些证据是否针对同一事项存在互相矛盾、不可同时成立的规定。"
        "不同事项（如年假天数与报销流程）不构成冲突；证据与问题无关或不足时判 false。"
        "只输出 JSON："
        '{"is_conflict": true|false, "claim_a": "或 null", "claim_b": "或 null", '
        '"evidence_ids": ["e1","e2"], "reason_code": '
        '"MUTUALLY_EXCLUSIVE_RULES|APPLICABILITY_AMBIGUITY|null"}'
    )
    content = _call(
        "你是制度冲突判定器。仅当两条及以上证据针对同一事项给出互相矛盾、"
        "不可同时成立的规定时才判 is_conflict=true；证据针对不同事项、与问题无关、"
        "或证据不足无法确定时，一律判 is_conflict=false。不裁决制度优先级，只输出 JSON。",
        user,
        _model("CHAT_MODEL"),
    )
    data = _parse_json(content)
    reason_code = _optional_str(data.get("reason_code"))
    reason_enum = None
    if reason_code is not None:
        try:
            reason_enum = ConflictReasonCode(reason_code)
        except ValueError:
            reason_enum = None
    return ConflictAssessmentDTO(
        is_conflict=bool(data.get("is_conflict", False)),
        claim_a=_optional_str(data.get("claim_a")),
        claim_b=_optional_str(data.get("claim_b")),
        evidence_ids=tuple(str(x) for x in data.get("evidence_ids", [])),
        reason_code=reason_enum,
    )


def _optional_str(value: Any) -> str | None:
    """把模型输出的 'null' 字符串归一为 None。"""
    if value in (None, "null", ""):
        return None
    return str(value)


def _extract_json_array(content: str) -> str:
    text = content.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)
    return text
