/* Auth endpoints: signup, login, current user. */
import { apiFetch } from "./client";

export function signup({ fullName, email, password }) {
  return apiFetch("/auth/signup", {
    method: "POST",
    body: { full_name: fullName, email, password },
  });
}

export function login({ email, password }) {
  return apiFetch("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function getMe(token) {
  return apiFetch("/auth/me", { token });
}
