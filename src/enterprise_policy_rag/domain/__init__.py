"""领域核心层（SPEC §2.1）。

只依赖 Python 标准库；禁止导入 FastAPI/Streamlit/Pydantic/SQLAlchemy/FAISS/
DashScope/MinerU 或任何网络/数据库库。
承载制度状态、版本选择、引用有效性、统一结果与错误码。
"""
