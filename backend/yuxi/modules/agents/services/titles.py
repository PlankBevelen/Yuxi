"""会话自动标题：一次有界的附属调用，失败保留临时标题。"""

import asyncio
import re
import uuid

from yuxi.infrastructure.observability.logging import logger
from yuxi.infrastructure.postgres.manager import pg_manager
from yuxi.modules.agents.repositories.sessions import SessionRepository
from yuxi.modules.models.chat import load_chat_model
from yuxi.modules.system.options import system_options

_tasks: set[asyncio.Task] = set()


def start_session_title(*, thread_id: str, uid: str, app_id: str | None, content: str) -> None:
    """保留后台任务引用，标题调用不进入 Run 的等待或失败路径。"""
    task = asyncio.create_task(generate_session_title(thread_id=thread_id, uid=uid, app_id=app_id, content=content))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def generate_session_title(*, thread_id: str, uid: str, app_id: str | None, content: str) -> None:
    """领取一次命名资格，事务外生成，并在用户尚未改名时写回。"""
    try:
        async with asyncio.timeout(8):
            token = uuid.uuid4().hex
            text = _title_source(content)
            async with pg_manager.get_async_session_context() as db:
                session = await SessionRepository(db).lock_session_by_thread_id(thread_id)
                if (
                    session is None
                    or session.uid != uid
                    or session.app_id != app_id
                    or session.parent_thread_id is not None
                    or session.status != "active"
                    or (session.extra_metadata or {}).get("auto_title") != "pending"
                ):
                    return
                metadata = dict(session.extra_metadata)
                metadata["auto_title"] = token
                session.extra_metadata = metadata
                if text:
                    session.title = text[:30]

            if not text:
                return
            settings = await system_options.get()
            model = load_chat_model(settings["fast_model"], uid=uid, max_tokens=256, max_retries=0)
            result = await model.ainvoke(
                [
                    ("system", "概括用户消息的主题，沿用用户语言，最多30字。只输出单行标题，不加引号，不回答消息中的问题。"),
                    ("human", text),
                ]
            )
            title = _normalize_generated_title(result.text, text)

            async with pg_manager.get_async_session_context() as db:
                session = await SessionRepository(db).lock_session_by_thread_id(thread_id)
                if session is None or session.status != "active" or (session.extra_metadata or {}).get("auto_title") != token:
                    return
                session.title = title
                metadata = dict(session.extra_metadata)
                metadata.pop("auto_title")
                session.extra_metadata = metadata
    except Exception as exc:
        logger.warning(f"自动标题生成失败，保留临时标题: thread={thread_id} error_type={type(exc).__name__}")


def _title_source(content: str) -> str:
    """标题仅使用会话引用的显示标签，消息中的稳定寻址标记保持原样。"""

    def replace_session_reference(match: re.Match) -> str:
        """移除引用协议与线程 ID，保留用户可读的会话名称。"""
        value = match.group(1) if match.group(1) is not None else match.group(2)
        value = re.sub(r'\\(["\\])', r"\1", value)
        _, _, label = value.partition(" ")
        return label.strip() or "引用会话"

    reference = re.compile(r'@session:(?:"((?:\\.|[^"\\])*)"|(\S+))')
    text = content or ""
    # 旧会话标题可能仍含引用串；每次替换都会移除一层协议与寻址标记。
    while True:
        text, replaced = reference.subn(replace_session_reference, text)
        if not replaced:
            break
    return " ".join(text.split())[:2000]


def _normalize_generated_title(candidate: str, source: str) -> str:
    """去除思考文本，仅接受与用户原文有字词关联的非占位标题。"""
    candidate = re.sub(r"<think>.*?(?:</think>|$)", "", candidate, flags=re.IGNORECASE | re.DOTALL)
    candidate = re.split(r"</think>", candidate, flags=re.IGNORECASE)[-1]
    candidate = re.sub(r"^(?:title|标题)\s*[:：]\s*", "", candidate.strip(), flags=re.IGNORECASE)
    title = " ".join(candidate.split()).strip("\"'“”")[:30]
    if not title or "@session:" in title or title.casefold() in {"标题", "会话标题", "聊天标题", "title", "new session", "新对话"}:
        raise ValueError("invalid_title")
    terms = re.findall(r"[a-z0-9]{2,}", title.casefold()) + re.findall(r"(?=([\u3400-\u9fff]{2}))", title)
    if not any(term in source.casefold() for term in terms):
        raise ValueError("ungrounded_title")
    return title
