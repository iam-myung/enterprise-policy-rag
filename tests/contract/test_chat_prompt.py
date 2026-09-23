"""Step 9-QA 补测：Prompt 合约（SPEC §9.3）——无思维链泄漏。

验收点：System 指令必须包含「禁止输出思维链 / 只依据 Evidence / 只能返回给定 ID」，
且 QwenChatModel 构造的 Prompt 确实传给 provider。
"""

from enterprise_policy_rag.adapters.llm.qwen_chat_model import (
    SYSTEM_INSTRUCTION,
    ChatPrompt,
    QwenChatModel,
    build_chat_prompt,
)
from enterprise_policy_rag.application.ports.models import ModelAnswerDTO
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerStatus


def _evidence(evidence_id: str = "e1") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        chunk_id=f"{evidence_id}-chunk",
        document_id="d1",
        title="年假制度",
        version="v1",
        page=1,
        char_start=0,
        char_end=5,
        quote="年假十五天",
        page_text_sha256="0" * 64,
        score=1.0,
    )


def test_system_instruction_forbids_chain_of_thought() -> None:
    """System 指令含禁止思维链与只依据 Evidence 的 guardrail。"""
    assert "思维链" in SYSTEM_INSTRUCTION
    assert "只依据" in SYSTEM_INSTRUCTION
    assert "不得使用外部常识" in SYSTEM_INSTRUCTION
    assert "NO_EVIDENCE" in SYSTEM_INSTRUCTION
    assert "CONFLICT" in SYSTEM_INSTRUCTION


def test_build_chat_prompt_binds_evidence_ids() -> None:
    """用户 Prompt 按 ID 编号 Evidence，且 system 指令含禁止思维链。"""
    prompt = build_chat_prompt("年假多少天", (_evidence("e1"), _evidence("e2")))
    assert "思维链" in prompt.system
    assert "e1" in prompt.user
    assert "e2" in prompt.user


def test_chat_model_passes_guarded_prompt_to_provider() -> None:
    """QwenChatModel 传给 provider 的 Prompt 必须含禁止思维链指令。"""
    received: list[ChatPrompt] = []

    def fake_provider(prompt: ChatPrompt) -> ModelAnswerDTO:
        received.append(prompt)
        return ModelAnswerDTO(
            status=AnswerStatus.ANSWERED,
            answer="年假十五天",
            citation_ids=("e1",),
            conflict_note=None,
        )

    model = QwenChatModel(fake_provider)
    result = model.generate("年假多少天", (_evidence("e1"),))
    assert result.status is AnswerStatus.ANSWERED
    assert received and "思维链" in received[0].system
