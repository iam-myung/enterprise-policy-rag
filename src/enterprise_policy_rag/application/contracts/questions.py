"""问答相关 DTO（SPEC §8.5 QuestionRequestDTO / QuestionAnswerDTO / CitationDTO）。"""

from pydantic import BaseModel, Field


class QuestionRequestDTO(BaseModel):
    """问题请求（SPEC §8.1 / §8.5）：question 1–1000，top_k 1–10 默认 5。"""

    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


class CitationDTO(BaseModel):
    """引用 DTO（SPEC §8.5）：source_url 由 API 生成，不采信模型/用户。"""

    evidence_id: str
    document_id: str
    title: str
    version: str
    effective_at: str | None = None
    page: int
    quote: str
    char_start: int
    char_end: int
    page_text_sha256: str
    source_url: str


class QuestionAnswerDTO(BaseModel):
    """问答响应 DTO（SPEC §8.5）。"""

    status: str
    answer: str
    citations: list[CitationDTO]
    warnings: list[str]
    corpus_revision: str
    confidence: float
    trace_id: str
