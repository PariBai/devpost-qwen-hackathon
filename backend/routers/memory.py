"""Memory route: the current user's long-term preferences (powers the memory panel)."""

from fastapi import APIRouter, Depends

from backend.security import get_current_user
from app.common.store import get_store
from app.common import memory as memory_utils

router = APIRouter(prefix="/me", tags=["memory"])


@router.get("/preferences")
async def get_preferences(user_id: str = Depends(get_current_user)):
    store = await get_store()
    prefs = await memory_utils.list_preferences(store, user_id)
    return {"user_id": user_id, "preferences": {p.key: p.value for p in prefs}}
