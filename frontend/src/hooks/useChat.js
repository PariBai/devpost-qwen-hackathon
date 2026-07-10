/*
 * Chat state machine for the signed-in user:
 *  - loads the sidebar chat list and a selected chat's history
 *  - creates a chat lazily on the first message (so "New conversation" just
 *    clears to the welcome hero without leaving empty chats around)
 *  - streams the assistant answer and appends chunks live
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  createChat,
  listChats,
  getMessages,
  deleteChat as apiDeleteChat,
  streamMessage,
} from "../api/chats";

// Local id for React keys. crypto.randomUUID() only exists in a secure context
// (HTTPS or localhost); on plain http://<ip> it's undefined, so fall back to a
// simple RFC4122-ish v4 generator. (These ids are UI-only — the server mints its
// own ids for chats and history rows.)
function newId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* fall through */
    }
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// A chat_history row (one Q+A) becomes a user message + an assistant message.
function rowsToMessages(rows) {
  const out = [];
  for (const r of rows) {
    out.push({ id: newId(), role: "user", text: r.question });
    out.push({ id: newId(), role: "assistant", text: r.answer });
  }
  return out;
}

export function useChat() {
  const { token } = useAuth();

  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [preferences, setPreferences] = useState({});

  const abortRef = useRef(null);

  const refreshChats = useCallback(async () => {
    try {
      setChats(await listChats(token));
    } catch {
      /* sidebar is non-critical; ignore transient errors */
    }
  }, [token]);

  useEffect(() => {
    refreshChats();
  }, [refreshChats]);

  const startNewChat = useCallback(() => {
    abortRef.current?.abort();
    setActiveChatId(null);
    setMessages([]);
  }, []);

  const selectChat = useCallback(
    async (chatId) => {
      if (chatId === activeChatId) return;
      abortRef.current?.abort();
      setActiveChatId(chatId);
      setMessages([]);
      setLoadingHistory(true);
      try {
        const rows = await getMessages(chatId, token);
        setMessages(rowsToMessages(rows));
      } catch {
        setMessages([]);
      } finally {
        setLoadingHistory(false);
      }
    },
    [activeChatId, token]
  );

  const removeChat = useCallback(
    async (chatId) => {
      try {
        await apiDeleteChat(chatId, token);
      } catch {
        /* ignore */
      }
      if (chatId === activeChatId) startNewChat();
      setChats((prev) => prev.filter((c) => c.chat_id !== chatId));
    },
    [activeChatId, token, startNewChat]
  );

  const updateLastAssistant = useCallback((updater) => {
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === "assistant") {
          next[i] = { ...next[i], ...updater(next[i]) };
          break;
        }
      }
      return next;
    });
  }, []);

  const send = useCallback(
    async (text) => {
      const message = text.trim();
      if (!message || sending) return;

      let chatId = activeChatId;
      if (!chatId) {
        try {
          const created = await createChat(token);
          chatId = created.chat_id;
          setActiveChatId(chatId);
        } catch {
          return;
        }
      }

      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "user", text: message },
        { id: newId(), role: "assistant", text: "", streaming: true },
      ]);
      setSending(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamMessage({
          chatId,
          token,
          message,
          signal: controller.signal,
          onEvent: (evt) => {
            if (evt.type === "text") {
              updateLastAssistant((m) => ({ text: m.text + evt.content }));
            } else if (evt.type === "memory") {
              // Live "🧠 remembered / 🗑 forgot" feed — group this turn's ops into
              // one memory entry that renders inline after the assistant answer.
              const op = {
                action: evt.action,
                key: evt.key,
                value: evt.value,
                reason: evt.reason,
              };
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last && last.role === "memory") {
                  next[next.length - 1] = { ...last, ops: [...last.ops, op] };
                } else {
                  next.push({ id: newId(), role: "memory", ops: [op] });
                }
                return next;
              });
            } else if (evt.type === "preferences") {
              setPreferences(evt.content || {});
            } else if (evt.type === "error") {
              updateLastAssistant((m) => ({
                text: m.text || "Sorry — something went wrong.",
                error: evt.content,
                streaming: false,
              }));
            }
          },
        });
      } catch (err) {
        if (err.name !== "AbortError") {
          updateLastAssistant((m) => ({
            text: m.text || "Sorry — I couldn't reach the assistant.",
            error: err.message,
            streaming: false,
          }));
        }
      } finally {
        updateLastAssistant(() => ({ streaming: false }));
        setSending(false);
        refreshChats();
      }
    },
    [activeChatId, sending, token, updateLastAssistant, refreshChats]
  );

  return {
    chats,
    activeChatId,
    messages,
    sending,
    loadingHistory,
    preferences,
    startNewChat,
    selectChat,
    removeChat,
    send,
  };
}
