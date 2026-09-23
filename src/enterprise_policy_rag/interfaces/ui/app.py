"""Streamlit Demo UI（SPEC §2.2 interfaces.ui）。

只调用 ApiClient，不直连数据库/索引/模型。
展示：文档处理状态区、问题输入、ANSWERED/NO_EVIDENCE/CONFLICT 三态答案与置信度、
引用（文件名/版本/页码/quote + 原文回看）、失败 Envelope 的可读提示。
"""

import json
import uuid
from collections.abc import Iterator
from typing import Any, cast

import streamlit as st
import streamlit.components.v1 as components

from enterprise_policy_rag.interfaces.ui.api_client import ApiClient, ApiError


def _effective_status(item: dict[str, Any]) -> str:
    """生效状态（SPEC §4.2：日期待确认显式提示）。"""
    if item.get("effective_at"):
        return str(item["effective_at"])
    return "待确认"


def render_documents(client: ApiClient) -> None:
    """文档处理状态区（SPEC §2.2 interfaces.ui）。"""
    st.subheader("制度文档")
    try:
        data = client.list_documents()
    except ApiError as exc:
        st.warning(f"无法加载文档列表：{exc.message}")
        return

    items = data.get("items", [])
    if not items:
        st.info("暂无已导入的制度文档。")
        return

    rows = [
        {
            "名称": item.get("title", ""),
            "版本": item.get("version", ""),
            "生效日期": _effective_status(item),
            "处理状态": item.get("status", ""),
            "页数": item.get("page_count", ""),
            "失败原因": item.get("error", "") or "-",
        }
        for item in items
    ]
    st.dataframe(rows, width="stretch")


_STATUS_META: dict[str, tuple[str, str, str]] = {
    "ANSWERED": ("✅ 已回答", "以下答案可直接采用", "#1a7f37"),
    "CONFLICT": ("⚠️ 制度冲突", "多份制度矛盾，请人工确认后再执行", "#b35900"),
    "NO_EVIDENCE": ("ℹ️ 无制度依据", "制度库未覆盖，建议咨询 HR 或补充文档", "#57606a"),
}


def _render_status_badge(status: str) -> None:
    """状态徽章 + 行动建议（一句话告诉用户下一步做什么）。"""
    badge, action, color = _STATUS_META.get(
        status, ("❓ 未知状态", "", "#57606a")
    )
    st.markdown(
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f'background:{color}1f;color:{color};font-weight:600;font-size:0.82rem;">'
        f'{badge}</span>&nbsp;'
        f'<span style="color:#8b949e;font-size:0.82rem;">{action}</span>',
        unsafe_allow_html=True,
    )


def _render_confidence(confidence: float) -> None:
    """置信度语义化：彩色进度条 + 等级 + 一句话解释。"""
    pct = min(max(confidence, 0.0), 1.0) * 100
    if confidence >= 0.7:
        level, color = "高", "#1a7f37"
    elif confidence >= 0.5:
        level, color = "中", "#b35900"
    else:
        level, color = "低", "#cf222e"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin:6px 0;">'
        f'<span style="color:#8b949e;font-size:0.82rem;">置信度</span>'
        f'<div style="flex:1;max-width:180px;background:#eaecef;'
        f'border-radius:999px;height:6px;">'
        f'<div style="width:{pct}%;background:{color};height:6px;'
        f'border-radius:999px;"></div></div>'
        f'<span style="color:{color};font-weight:600;font-size:0.82rem;">'
        f'{confidence * 100:.0f}%（{level}）</span></div>'
        f'<span style="color:#8b949e;font-size:0.76rem;">可直接采信的程度</span>',
        unsafe_allow_html=True,
    )


def _render_citations(
    client: ApiClient, citations: list[dict[str, Any]]
) -> None:
    """引用证据卡：标题/版本/页码 + quote + 原文回看。"""
    st.markdown("**📎 引用依据**")
    for i, citation in enumerate(citations, 1):
        title = citation.get("title", "")
        version = citation.get("version", "")
        page = citation.get("page", "")
        quote = citation.get("quote", "")
        source_url = citation.get("source_url", "")
        with st.container(border=True):
            st.markdown(
                f"**{i}. {title}**　"
                f"<span style='color:#8b949e;font-size:0.82rem;'>"
                f"v{version} · 第 {page} 页</span>",
                unsafe_allow_html=True,
            )
            st.write_stream(_stream_text(f"> {quote}"))
            if source_url:
                st.markdown(f"[查看原文 →]({client.absolute_url(source_url)})")


def _stream_text(text: str) -> Iterator[str]:
    """一次性 yield 全文，配合 st.write_stream 立即渲染。"""
    yield text


def _render_stream_answer(answer: str) -> None:
    """立即渲染答案正文。"""
    st.write_stream(_stream_text(answer))


def render_answer(client: ApiClient, result: dict[str, Any]) -> None:
    """答案渲染：状态徽章 + 正文 + 置信度 + 引用（SPEC §4.3 / §8.5）。"""
    raw_status = result.get("status")
    status = raw_status if isinstance(raw_status, str) else ""
    answer = result.get("answer", "")
    citations = result.get("citations", [])

    _render_status_badge(status)

    if answer:
        _render_stream_answer(answer)
    elif status == "NO_EVIDENCE":
        st.markdown("未找到制度依据，无法回答该问题。")

    # 拒答不展示置信度，避免「0% 低」被误解为模型乱答。
    confidence = result.get("confidence")
    if status != "NO_EVIDENCE" and confidence is not None:
        _render_confidence(float(confidence))

    warnings = result.get("warnings", [])
    if warnings:
        st.caption("警告：" + "；".join(warnings))

    if citations:
        _render_citations(client, citations)


_EXAMPLES = (
    "员工年假有多少天？",
    "报销需要提交哪些材料？",
    "公司食堂几点开饭？",
)


def _active_session() -> dict[str, Any] | None:
    """获取当前激活会话。"""
    sid = st.session_state.get("active_session_id")
    for s in st.session_state.get("sessions", []):
        session = cast(dict[str, Any], s)
        if session["id"] == sid:
            return session
    return None


def _new_session() -> dict[str, Any]:
    """创建新会话并激活。"""
    sid = uuid.uuid4().hex[:8]
    session: dict[str, Any] = {"id": sid, "title": "新对话", "messages": []}
    st.session_state.setdefault("sessions", []).append(session)
    st.session_state.active_session_id = sid
    return session


def _ask_now(client: ApiClient, question: str) -> None:
    """触发一轮问答：写入当前激活会话，st.rerun 由历史循环统一渲染。"""
    session = _active_session() or _new_session()
    if session["title"] == "新对话":
        session["title"] = question[:20] + ("…" if len(question) > 20 else "")
    session["messages"].append({"role": "user", "content": question})
    try:
        with st.spinner("检索与生成中…"):
            result = client.ask(question)
    except ApiError as exc:
        session["messages"].append(
            {"role": "assistant", "error": exc.message}
        )
    else:
        session["messages"].append(
            {"role": "assistant", "result": result}
        )
    st.rerun()


_CSS = """
<style>
    /* 底部输入框圆角，贴近主流 AI 客户端 */
    .stChatInput textarea { border-radius: 16px; }
    /* 隐藏 Streamlit 自带的 Deploy 按钮（与本应用无关） */
    [data-testid="stAppDeployButton"] { display: none; }
</style>
"""


def _inject_chat_input_text(text: str) -> None:
    """把示例题写入 st.chat_input 的 textarea（React 受控输入需改原生 value + input 事件）。"""
    payload = json.dumps(text, ensure_ascii=False)
    components.html(
        f"""
        <script>
        (function() {{
          const text = {payload};
          const doc = window.parent.document;
          function fill(attempt) {{
            const ta = doc.querySelector(
              'textarea[data-testid="stChatInputTextArea"],'
              + ' [data-testid="stChatInput"] textarea,'
              + ' .stChatInput textarea'
            );
            if (!ta) {{
              if (attempt < 40) setTimeout(function() {{ fill(attempt + 1); }}, 50);
              return;
            }}
            const proto = window.parent.HTMLTextAreaElement.prototype;
            const desc = Object.getOwnPropertyDescriptor(proto, "value");
            const tracker = ta._valueTracker;
            if (tracker) tracker.setValue("");
            if (desc && desc.set) desc.set.call(ta, text);
            else ta.value = text;
            ta.dispatchEvent(new Event("input", {{ bubbles: true }}));
            ta.dispatchEvent(new Event("change", {{ bubbles: true }}));
            ta.focus();
            ta.selectionStart = ta.selectionEnd = text.length;
          }}
          fill(0);
        }})();
        </script>
        """,
        height=0,
    )


def _render_welcome() -> None:
    """空会话欢迎区：能力说明 + 示例题（点击填入底部输入框，回车发送）。"""
    st.caption("基于企业制度 PDF 的检索增强问答")
    st.markdown(
        "- ✅ 基于最新制度 PDF 回答，答案可回看原文出处\n"
        "- ⚠️ 多份制度冲突时会明确标注，不武断下结论\n"
        "- 🚫 证据不足会拒答，而非凭空编造"
    )
    st.caption("💡 试试这些问题（点击填入下方输入框，再按回车发送）：")
    cols = st.columns(len(_EXAMPLES))
    for col, q in zip(cols, _EXAMPLES, strict=True):
        with col, st.container(border=True):
            if st.button(q, key=f"welcome_{q}", use_container_width=True):
                st.session_state["question_draft"] = q
                st.rerun()


def main() -> None:
    """Streamlit 入口（类 ChatGPT 客户端布局 + 多会话管理）。"""
    st.set_page_config(
        page_title="企业制度 ChatBot",
        page_icon="💼",
        layout="centered",
    )
    st.markdown(_CSS, unsafe_allow_html=True)

    client = ApiClient()

    st.session_state.setdefault("sessions", [])
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("question_draft", "")
    if st.session_state.active_session_id is None and st.session_state.sessions:
        st.session_state.active_session_id = st.session_state.sessions[0]["id"]

    active = _active_session()

    # 侧边栏：新对话 / 对话记录 / 文档
    with st.sidebar:
        st.title("💼 企业制度 ChatBot")
        if st.button("🆕 新对话", use_container_width=True):
            _new_session()
            st.rerun()
        st.divider()
        st.caption("对话记录")
        for s in reversed(st.session_state.sessions):
            sid = s["id"]
            title = s["title"]
            is_active = sid == st.session_state.active_session_id
            label = f"{'●' if is_active else '○'}  {title}"
            if st.button(label, key=f"session_{sid}", use_container_width=True):
                st.session_state.active_session_id = sid
                st.rerun()
        st.divider()
        with st.expander("📚 已导入文档", expanded=False):
            render_documents(client)

    messages = active["messages"] if active else []

    st.markdown("## 企业制度问答系统")
    if active and messages:
        st.caption(f"📍 当前对话：{active['title']}")

    # 欢迎区仅在空会话展示，避免挤占答案阅读区。
    if not messages:
        _render_welcome()

    # pending（兼容旧触发路径）
    if pending := st.session_state.pop("_pending_question", None):
        _ask_now(client, pending)

    # 历史消息（用户 / 助手统一聊天气泡）
    for msg in messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        elif "error" in msg:
            with st.chat_message("assistant"):
                st.error(msg["error"])
        else:
            with st.chat_message("assistant"):
                render_answer(client, msg["result"])

    # 底部 chat_input：原生支持回车发送
    draft = str(st.session_state.get("question_draft", "")).strip()
    prompt = st.chat_input("请输入你的问题…")
    if draft:
        _inject_chat_input_text(draft)

    if prompt and prompt.strip():
        st.session_state["question_draft"] = ""
        _ask_now(client, prompt.strip())


if __name__ == "__main__":
    main()
