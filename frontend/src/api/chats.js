/* Chat endpoints: CRUD over conversations + the streamed message endpoint.
 *
 * The send endpoint is POST + Bearer auth, so EventSource (GET-only) can't be
 * used — we read the SSE stream manually from the fetch body reader. */
import { API_BASE, apiFetch, ApiError } from "./client";

export function createChat(token) {
  return apiFetch("/chats", { method: "POST", token });
}

export function listChats(token) {
  return apiFetch("/chats", { token });
}

export function getMessages(chatId, token) {
  return apiFetch(`/chats/${chatId}/messages`, { token });
}

export function renameChat(chatId, title, token) {
  return apiFetch(`/chats/${chatId}`, { method: "PATCH", body: { title }, token });
}

export function deleteChat(chatId, token) {
  return apiFetch(`/chats/${chatId}`, { method: "DELETE", token });
}

/*
 * Stream one message. Calls `onEvent` for each SSE payload:
 *   { type: "text", content }         -> a streamed answer chunk
 *   { type: "preferences", content }  -> updated memory after the turn
 *   { type: "error", content }        -> backend error
 *   { type: "end" }                   -> stream finished
 * Pass an AbortSignal to cancel an in-flight stream.
 */
export async function streamMessage({ chatId, token, message, onEvent, signal }) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      /* keep generic */
    }
    throw new ApiError(detail, res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!raw.startsWith("data:")) continue;
      try {
        onEvent(JSON.parse(raw.slice(5).trim()));
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
