/* Long-term memory endpoints: read + forget the user's stored preferences. */
import { apiFetch } from "./client";

export async function getPreferences(token) {
  const data = await apiFetch("/me/preferences", { token });
  return data.preferences || {};
}

export function forgetPreference(key, token) {
  return apiFetch(`/me/preferences/${encodeURIComponent(key)}`, {
    method: "DELETE",
    token,
  });
}
