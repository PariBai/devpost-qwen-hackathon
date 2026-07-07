/*
 * Thin fetch wrapper around the FastAPI backend.
 * - Base URL comes from VITE_API_BASE (see .env.example), default = ECS deployment.
 * - Attaches the Bearer token when one is passed.
 * - Throws an Error carrying the backend's `detail` message on non-2xx responses.
 */

// VITE_API_BASE resolution:
//   unset            -> ECS default (handy for `npm run dev` with no .env)
//   "/" or ""        -> same-origin (reverse-proxied behind nginx in Docker)
//   "http://host:port" -> that absolute backend
const _rawBase = import.meta.env.VITE_API_BASE;
export const API_BASE = (_rawBase ?? "http://47.84.234.2:8086").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection.", 0);
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return null;
  return res.json();
}
