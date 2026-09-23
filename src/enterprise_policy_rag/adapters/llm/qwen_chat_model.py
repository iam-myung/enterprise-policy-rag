"""Qwen 回答模型适配器（SPEC §5.318 / §9.3）。

实现 ChatModelPort：构造含「禁止思维链」等 System 指令的 Prompt，调用 Provider 生成
结构化答案；只能引用已给定 evidence ID；Provider 失败映射安全异常。
"""

from collections.abc import Callable
from dataclasses import dataclass

from enterprise_policy_rag.application.ports.models import ModelAnswerDTO
from enterprise_policy_rag.domain.citation_rules import CitationValidationError
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import AppError, ErrorCode


class ChatModelError(AppError):
    """回答模型 Provider 失败 → 502 LLM_PROVIDER_ERROR（SPEC §6.2）。"""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.LLM_PROVIDER_ERROR, message)


@dataclass(frozen=True)
class ChatPrompt:
    """问答 Prompt DTO（SPEC §9.3）：system 指令 + 用户输入。"""

    system: str
    user: str


# SPEC §9.3 System 指令：只依据 Evidence / 证据不足 NO_EVIDENCE / 冲突 CONFLICT /
# 不得使用外部常识 / 不得输出思维链 / 只能返回给定 evidence IDs。
SYSTEM_INSTRUCTION: str = (
    "你是企业内部制度问答助手，必须严格遵守以下规则：\n"
    "1. 只依据下方提供的 Evidence 回答问题，不得使用外部常识补全制度内容。\n"
    "2. 证据不足时 status 返回 NO_EVIDENCE，answer 置空。\n"
    "3. 多条现行制度证据语义冲突时 status 返回 CONFLICT，并填写 conflict_note。\n"
    "4. 禁止输出思维链、推理过程或任何中间步骤，只输出最终结论。\n"
    "5. citation_ids 只能引用输入 Evidence 中给出的 evidence ID，不得编造页码或原文。"
)


def build_chat_prompt(
    question: str, evidences: tuple[Evidence, ...]
) -> ChatPrompt:
    """按 SPEC §9.3 构造 Prompt：system 指令 + question + 按 ID 编号的 Evidence。"""
    evidence_lines = [f"Evidence[{e.evidence_id}]: {e.quote}" for e in evidences]
    user = f"问题：{question}\n" + "\n".join(evidence_lines)
    return ChatPrompt(system=SYSTEM_INSTRUCTION, user=user)


class QwenChatModel:
    """Qwen 回答模型适配器。

    provider：可调用，输入构造好的 ChatPrompt 返回结构化 ModelAnswerDTO。
    """

    def __init__(
        self,
        provider: Callable[[ChatPrompt], ModelAnswerDTO],
    ) -> None:
        self._provider = provider

    def generate(
        self, question: str, evidences: tuple[Evidence, ...]
    ) -> ModelAnswerDTO:
        given_ids = {e.evidence_id for e in evidences}
        prompt = build_chat_prompt(question, evidences)
        try:
            answer = self._provider(prompt)
        except Exception as exc:
            raise ChatModelError("回答模型 Provider 失败") from exc
        if not set(answer.citation_ids).issubset(given_ids):
            raise CitationValidationError("回答模型返回未知 evidence ID")
        return answer
