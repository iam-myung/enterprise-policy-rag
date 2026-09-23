"""Streamlit UI headless smoke（SPEC §11 / §13.1）。

用 AppTest 渲染 UI，mock ApiClient 避免真实网络；验证标题、文档区、
示例题填入、chat_input 回车发送、拒答不展示置信度。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

APP_PATH = str(
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "enterprise_policy_rag"
    / "interfaces"
    / "ui"
    / "app.py"
)


def _run_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=10)


def test_ui_renders_title_and_empty_documents() -> None:
    with patch("enterprise_policy_rag.interfaces.ui.api_client.ApiClient") as mock_cls:
        mock_cls.return_value.list_documents.return_value = {
            "items": [],
            "corpus_revision": "rev-1",
        }
        at = _run_app()
        at.run()
        assert not at.exception
        assert at.title[0].value == "💼 企业制度 ChatBot"
        labels = [b.label for b in at.button]
        assert "公司食堂几点开饭？" in labels
        assert len(at.chat_input) >= 1


def test_ui_renders_documents_table() -> None:
    with patch("enterprise_policy_rag.interfaces.ui.api_client.ApiClient") as mock_cls:
        mock_cls.return_value.list_documents.return_value = {
            "items": [
                {
                    "title": "考勤管理制度",
                    "version": "2024.01",
                    "effective_at": None,
                    "status": "ACTIVE",
                    "page_count": 7,
                    "error": None,
                }
            ],
            "corpus_revision": "rev-1",
        }
        at = _run_app()
        at.run()
        assert not at.exception
        assert len(at.dataframe) >= 1


def test_ui_example_fills_then_chat_input_sends() -> None:
    """示例题只填入不提问；chat_input 提交后才提问；拒答不渲染置信度。"""
    with patch("enterprise_policy_rag.interfaces.ui.api_client.ApiClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        client.list_documents.return_value = {
            "items": [],
            "corpus_revision": "rev-1",
        }
        client.ask.return_value = {
            "status": "NO_EVIDENCE",
            "answer": "",
            "citations": [],
            "warnings": [],
            "corpus_revision": "rev-1",
            "confidence": 0.0,
        }
        client.absolute_url.side_effect = lambda p: f"http://127.0.0.1:8001{p}"

        at = _run_app()
        at.run()
        assert not at.exception

        example = next(b for b in at.button if b.label == "公司食堂几点开饭？")
        example.click().run()
        assert not at.exception
        client.ask.assert_not_called()
        assert at.session_state["question_draft"] == "公司食堂几点开饭？"

        # 回车发送路径：chat_input.set_value 模拟提交
        at.chat_input[0].set_value("公司食堂几点开饭？").run()
        assert not at.exception
        client.ask.assert_called_once_with("公司食堂几点开饭？")

        markdown_text = "\n".join(m.value for m in at.markdown)
        assert "未找到制度依据" in markdown_text
        assert "置信度" not in markdown_text
        assert "0%" not in markdown_text
