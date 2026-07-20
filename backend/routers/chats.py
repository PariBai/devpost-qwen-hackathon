"""
Chat routes: create/list/delete/rename chats, fetch a chat's message history, and
send a message (streamed answer via SSE, persisted as a Q+A row).

chat_id doubles as the LangGraph thread_id, so the agent keeps per-chat context via
the checkpointer while chat_history stores the displayable Q+A for the UI.
"""

import os
import uuid
import json
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.db import get_pool
from backend.security import get_current_user
from backend.schemas import MessageRequest, RenameRequest

from app.common.utils import get_active_qwen_model
from app.common.context import SessionContext
from app.common.store import get_store
from app.common import memory as memory_utils
from app.graph.compile import get_compiled_agent

router = APIRouter(tags=["chats"])

AGENT_NAME = "psx_agent"


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chats")
async def create_chat(user_id: str = Depends(get_current_user)):
    """Start a new (empty) conversation and return its id."""
    pool = await get_pool()
    chat_id = str(uuid.uuid4())
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO chats (id, user_id) VALUES (%s, %s)", (chat_id, user_id)
        )
    return {"chat_id": chat_id, "title": "New Chat"}


@router.get("/chats")
async def list_chats(user_id: str = Depends(get_current_user)):
    """List the user's chats, most-recent first (sidebar)."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, title, updated_at FROM chats WHERE user_id = %s ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
    return [
        {"chat_id": str(r["id"]), "title": r["title"], "updated_at": r["updated_at"].isoformat()}
        for r in rows
    ]


@router.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: str, user_id: str = Depends(get_current_user)):
    """Return all Q+A for a chat, ordered by qid (to re-render a past conversation)."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id)
        )
        if not await cur.fetchone():
            raise HTTPException(404, "chat not found")
        cur = await conn.execute(
            "SELECT qid, question, answer, attachments, created_at FROM chat_history "
            "WHERE chat_id = %s ORDER BY qid",
            (chat_id,),
        )
        rows = await cur.fetchall()
    return [
        {
            "qid": r["qid"],
            "question": r["question"],
            "answer": r["answer"],
            # attachments is a JSON array of chart image URLs (empty list if none).
            "attachments": _load_attachments(r.get("attachments")),
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


def _load_attachments(raw) -> list:
    """Parse the stored attachments column (JSON array text) into a list, tolerantly."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except Exception:
        return []


@router.patch("/chats/{chat_id}")
async def rename_chat(chat_id: str, body: RenameRequest, user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE chats SET title = %s WHERE id = %s AND user_id = %s",
            (body.title.strip() or "New Chat", chat_id, user_id),
        )
    return {"chat_id": chat_id, "title": body.title}


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id)
        )

    # Remove this chat's chart images (charts/<user_id>/<chat_id>/...). Best-effort.
    try:
        import shutil
        charts_dir = os.getenv("CHARTS_DIR", "charts")
        chat_charts = os.path.join(charts_dir, user_id, chat_id)
        if os.path.isdir(chat_charts):
            shutil.rmtree(chat_charts, ignore_errors=True)
    except Exception as e:
        print(f"[delete_chat] chart cleanup skipped for {chat_id}: {e}")

    # The chats/chat_history rows are gone (chat_history cascades). The LangGraph
    # checkpointer keeps this thread's agent state in ITS OWN tables (checkpoints,
    # checkpoint_writes, checkpoint_blobs), keyed by thread_id == chat_id, with no
    # FK to `chats` — so purge them here or they'd be orphaned. Best-effort: a
    # cleanup failure must not fail the delete the user already asked for.
    if os.getenv("DB_URL") or os.getenv("DB_URL_LOCAL"):
        try:
            from app.common.checkpointer import get_postgres_checkpointer

            cp = await get_postgres_checkpointer()
            if hasattr(cp, "adelete_thread"):
                await cp.adelete_thread(chat_id)
        except Exception as e:
            print(f"[delete_chat] checkpoint cleanup skipped for {chat_id}: {e}")

    return {"deleted": chat_id}


async def _next_qid(pool, chat_id: str) -> int:
    """The qid the NEXT Q+A row will get. Computed before streaming so the make_graph
    tool can name chart files with the real qid (charts/<uid>/<cid>/<qid>_chartN.png)."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT COALESCE(MAX(qid), 0) + 1 AS next FROM chat_history WHERE chat_id = %s",
            (chat_id,),
        )
        return (await cur.fetchone())["next"]


async def _save_qa(pool, chat_id: str, user_id: str, question: str, answer: str,
                   title: str, qid: int, attachments: list):
    """Append one Q+A row (at the pre-computed qid) and keep title/updated_at current."""
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO chat_history (id, chat_id, user_id, qid, question, answer, attachments) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), chat_id, user_id, qid, question, answer,
             json.dumps(attachments or [])),
        )
        # First message sets the chat title from the question; always bump updated_at.
        if qid == 1 and (title or "").strip() in ("", "New Chat"):
            new_title = question.strip()[:40] or "New Chat"
            await conn.execute(
                "UPDATE chats SET title = %s, updated_at = now() WHERE id = %s",
                (new_title, chat_id),
            )
        else:
            await conn.execute(
                "UPDATE chats SET updated_at = now() WHERE id = %s", (chat_id,)
            )


@router.post("/chats/{chat_id}/message")
async def send_message(
    chat_id: str, body: MessageRequest, user_id: str = Depends(get_current_user)
):
    """Stream the agent's answer (SSE) and persist the Q+A when done."""
    pool = await get_pool()

    # Verify the chat belongs to this user BEFORE streaming.
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT title FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id)
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "chat not found")
    title = row["title"]

    # The qid this turn will become — computed up front so make_graph names chart files
    # deterministically and _save_qa reuses the SAME qid (no double MAX+1 race).
    qid = await _next_qid(pool, chat_id)

    async def gen():
        full = ""
        try:
            agent = await get_compiled_agent(AGENT_NAME)
            context = SessionContext(
                thread_id=chat_id,        # chat_id == thread_id -> per-chat agent context
                user_id=user_id,          # stable cross-session memory key
                model=get_active_qwen_model(),
                agents=None,
                qid=qid,                  # for make_graph chart file names
                images=[],                # fresh per turn: last turn's charts never leak in
            )
            config = {"configurable": {"thread_id": chat_id}}

            async for chunk in agent.astream(
                {"messages": [{"role": "user", "content": body.message}]},
                stream_mode="custom",
                context=context,
                config=config,
            ):
                if not chunk:
                    continue
                agents = context.agents or []
                if agents == ["compliance_node"]:
                    piece = chunk.get("compliance_chunk")
                elif agents == ["finance_node"]:
                    piece = chunk.get("finance_chunk")
                else:
                    piece = chunk.get("synthesize_chunk")
                if piece:
                    full += piece
                    yield _sse({"type": "text", "content": piece})

            # Charts produced this turn by make_graph (finance/compliance decided a visual
            # helped). Stream them so the UI renders them right after the text answer.
            images = context.images or []
            if images:
                yield _sse({"type": "images", "items": images})

            # Recall trace (READ path): which stored memories were considered vs actually
            # injected this turn — the visible proof of relevance-based recall.
            if context.recalled:
                yield _sse({"type": "recall", "items": context.recalled})

            # Live memory feed: what the agent remembered/forgot THIS turn (with the
            # reason), so the UI can show "🧠 remembered / 🗑 forgot" as it happens.
            for op in (context.memory_ops or []):
                yield _sse({
                    "type": "memory",
                    "action": "remembered" if op.get("action") == "upsert" else "forgot",
                    "key": op.get("key"),
                    "value": op.get("value"),
                    "reason": op.get("reason"),
                })

            # Push updated preferences for the memory panel.
            try:
                store = await get_store()
                prefs = await memory_utils.list_preferences(store, user_id)
                yield _sse({"type": "preferences", "content": {p.key: p.value for p in prefs}})
            except Exception:
                pass

            # Persist the Q+A (with any chart URLs) for UI re-rendering.
            await _save_qa(pool, chat_id, user_id, body.message, full, title, qid, images)
            yield _sse({"type": "end"})

        except Exception as e:
            traceback.print_exc()
            yield _sse({"type": "error", "content": str(e)})
            yield _sse({"type": "end"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
