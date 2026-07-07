/* Avatar button that opens a small menu: identity, Preferences, Sign out.
 * Replaces the design's "Sign in / Open account" buttons for a logged-in user. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Avatar from "../Avatar";
import { useAuth } from "../../context/AuthContext";
import { PrefsIcon, SignOutIcon } from "../icons";

export default function UserMenu() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="user-menu" ref={ref}>
      <button
        className="user-menu__btn"
        onClick={() => setOpen((v) => !v)}
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Avatar user={user} size={34} />
      </button>

      {open && (
        <div className="user-menu__pop" role="menu">
          <div className="user-menu__id">
            {user?.fullName && <div className="user-menu__name">{user.fullName}</div>}
            <div className="user-menu__email">{user?.email}</div>
          </div>
          <button
            className="user-menu__item"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              navigate("/preferences");
            }}
          >
            <PrefsIcon />
            Preferences
          </button>
          <button
            className="user-menu__item user-menu__item--danger"
            role="menuitem"
            onClick={() => {
              signOut();
              navigate("/", { replace: true });
            }}
          >
            <SignOutIcon />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
