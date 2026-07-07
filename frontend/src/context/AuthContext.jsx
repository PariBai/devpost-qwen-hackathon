/*
 * Auth state: holds the JWT + user profile, persisted to localStorage so a
 * refresh keeps you signed in. The user_id inside the token is the stable
 * cross-session key the backend uses to namespace long-term memory.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "hikmat_auth";
const AuthContext = createContext(null);

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(readStored);

  useEffect(() => {
    if (auth) localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    else localStorage.removeItem(STORAGE_KEY);
  }, [auth]);

  const value = useMemo(
    () => ({
      token: auth?.token || null,
      user: auth?.user || null,
      isAuthed: Boolean(auth?.token),
      // Called with the backend AuthResponse ({ token, user_id, email, full_name }).
      signIn: (res) =>
        setAuth({
          token: res.token,
          user: {
            userId: res.user_id,
            email: res.email,
            fullName: res.full_name,
          },
        }),
      signOut: () => setAuth(null),
    }),
    [auth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
