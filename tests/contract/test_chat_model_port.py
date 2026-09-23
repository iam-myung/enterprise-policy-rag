"""Step 9-RED：ChatModelPort 契约测试（SPEC §5.318 / §9.3）。

验收点③：ChatModelPort 只引用给定 evidence ids；输出经结构化校验。
"""

from dataclasses import FrozenInstanceError

import pytest

from enterprise_policy_rag.application.ports.models import (
    ChatModelPort,
    ModelAnswerDTO,
)
from enterprise_policy_rag.domain.result import AnswerStatus


def test_model_answer_fields() -> None:
    """ModelAnswerDTO 字段：status/answer/citation_ids/conflict_note（SPEC §9.3）。"""
    dto = ModelAnswerDTO(
        status=AnswerStatus.ANSWERED,
        answer="年假为 15 天",
        citation_ids=("e1", "e2"),
        conflict_note=None,
    )
    assert dto.status is AnswerStatus.ANSWERED
    assert dto.answer == "年假为 15 天"
    assert dto.citation_ids == ("e1", "e2")
    assert dto.conflict_note is None


def test_model_answer_conflict_fields() -> None:
    """CONFLICT 状态携带 conflict_note 与互斥 claim 的 citation ids。"""
    dto = ModelAnswerDTO(
        status=AnswerStatus.CONFLICT,
        answer="",
        citation_ids=("e1", "e2"),
        conflict_note="两份制度对年假天数规定不一致",
    )
    assert dto.status is AnswerStatus.CONFLICT
    assert dto.conflict_note is not None


def test_model_answer_is_immutable() -> None:
    """ModelAnswerDTO 不可变。"""
    dto = ModelAnswerDTO(
        status=AnswerStatus.NO_EVIDENCE,
        answer="",
        citation_ids=(),
        conflict_note=None,
    )
    with pytest.raises(FrozenInstanceError):
        dto.answer = "x"  # type: ignore[misc]


def test_chat_model_port_declares_generate() -> None:
    """ChatModelPort 协议必须声明 generate 方法（SPEC §5.318）。"""
    assert hasattr(ChatModelPort, "generate")
