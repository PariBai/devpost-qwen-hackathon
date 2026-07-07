/*
 * Preferences / long-term memory page — the heart of the memory-agent story.
 * Lists every preference the agent has learned (from GET /me/preferences) as a
 * humanized key–value card, lets the user forget any of them, and explains that
 * these were captured automatically from how the user asks questions.
 */
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import TopNav from "../components/chat/TopNav";
import { BackIcon, TrashIcon } from "../components/icons";
import { useAuth } from "../context/AuthContext";
import { getPreferences, forgetPreference } from "../api/memory";

import "../styles/chat.css";
import "../styles/preferences.css";

// ---- display helpers -------------------------------------------------------

function humanize(key) {
  const s = String(key).replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// A little emoji per common preference category (falls back to the memory icon).
const EMOJI_RULES = [
  [/lang/i, "🌐"],
  [/sector/i, "📊"],
  [/risk/i, "🛡️"],
  [/currenc/i, "💱"],
  [/dividend|yield/i, "💰"],
  [/shariah|halal|complian/i, "✅"],
  [/invest|style|strateg/i, "📈"],
  [/budget|capital|amount/i, "💵"],
  [/horizon|term|timeframe|duration/i, "⏳"],
  [/broker/i, "🏦"],
  [/detail|verbos|length|format|tone/i, "🗣️"],
];

function emojiFor(key) {
  for (const [re, emoji] of EMOJI_RULES) if (re.test(key)) return emoji;
  return "🧠";
}

function isPrimitive(v) {
  return v === null || typeof v !== "object";
}

// Tidy raw scalar values for display: "long_term" -> "Long term", "banking" ->
// "Banking". Leave anything with an uppercase letter untouched so tickers and
// acronyms survive (UBL, MCB, USD/PKR, P/E).
function prettyScalar(v) {
  if (typeof v !== "string") return String(v);
  if (/[A-Z]/.test(v)) return v;
  const s = v.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function primitiveText(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) {
    return v.map((x) => (isPrimitive(x) ? prettyScalar(x) : JSON.stringify(x))).join(", ");
  }
  if (isPrimitive(v)) return prettyScalar(v);
  return JSON.stringify(v);
}

// Generic wrapper keys we can unwrap so "{ value: 'urdu' }" reads as just "urdu".
const GENERIC_KEYS = new Set(["value", "preference", "pref", "val", "setting"]);

function ValueView({ prefKey, value }) {
  if (value === null || value === undefined) {
    return <div className="pref-card__value">—</div>;
  }
  if (isPrimitive(value) || Array.isArray(value)) {
    return <div className="pref-card__value">{primitiveText(value)}</div>;
  }

  const entries = Object.entries(value);

  // Single-entry object -> show the inner value directly when the sub-key is
  // redundant with the preference name (generic wrapper, exact match, or one
  // name contains the other). e.g. investment_horizon:{horizon:"long_term"}.
  if (entries.length === 1) {
    const [k, v] = entries[0];
    const kl = k.toLowerCase();
    const pl = String(prefKey).toLowerCase();
    const redundant =
      GENERIC_KEYS.has(kl) || kl === pl || pl.includes(kl) || kl.includes(pl);
    if (redundant && (isPrimitive(v) || Array.isArray(v))) {
      return <div className="pref-card__value">{primitiveText(v)}</div>;
    }
  }

  // Multi-field object -> compact sub key/value list.
  return (
    <div className="pref-kv">
      {entries.map(([k, v]) => (
        <div className="pref-kv__row" key={k}>
          <span className="pref-kv__k">{humanize(k)}</span>
          <span className="pref-kv__v">{primitiveText(v)}</span>
        </div>
      ))}
    </div>
  );
}

// ---- page ------------------------------------------------------------------

export default function Preferences() {
  const navigate = useNavigate();
  const { token } = useAuth();

  const [prefs, setPrefs] = useState({});
  const [status, setStatus] = useState("loading"); // loading | ready | error

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setPrefs(await getPreferences(token));
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onForget = async (key) => {
    const prev = prefs;
    // Optimistic remove; restore on failure.
    const next = { ...prefs };
    delete next[key];
    setPrefs(next);
    try {
      await forgetPreference(key, token);
    } catch {
      setPrefs(prev);
    }
  };

  const keys = Object.keys(prefs);

  return (
    <div className="prefs-page">
      <TopNav />

      <div className="prefs-scroll">
        <div className="prefs-container">
          <button className="prefs-back" onClick={() => navigate("/chat")}>
            <BackIcon /> Back to chat
          </button>

          <div className="prefs-badge">🧠 Long-term memory</div>
          <h1 className="prefs-title">What Hikmat PSX remembers about you</h1>
          <p className="prefs-lead">
            These are the preferences the assistant has learned from your
            conversations. They shape every answer you get — your language, how
            you invest, the sectors you care about, and more.
          </p>

          {status === "ready" && keys.length > 0 && (
            <span className="prefs-count">
              {keys.length} preference{keys.length === 1 ? "" : "s"} remembered
            </span>
          )}

          {/* Loading */}
          {status === "loading" && (
            <div className="prefs-state">
              <div className="prefs-state__emoji">🧠</div>
              <div className="prefs-state__title">Loading your memory…</div>
            </div>
          )}

          {/* Error */}
          {status === "error" && (
            <div className="prefs-state">
              <div className="prefs-state__emoji">⚠️</div>
              <div className="prefs-state__title">Couldn't load your preferences</div>
              <p className="prefs-state__text">
                Something went wrong reaching the server. Please try again.
              </p>
              <button className="prefs-retry" onClick={load}>
                Retry
              </button>
            </div>
          )}

          {/* Empty */}
          {status === "ready" && keys.length === 0 && (
            <div className="prefs-state">
              <div className="prefs-state__emoji">🌱</div>
              <div className="prefs-state__title">Nothing remembered yet</div>
              <p className="prefs-state__text">
                As you chat, Hikmat PSX will pick up things like your preferred
                language, investment style, and sectors of interest — and show
                them here automatically.
              </p>
            </div>
          )}

          {/* Preference cards */}
          {status === "ready" && keys.length > 0 && (
            <div className="prefs-grid">
              {keys.map((key) => (
                <div className="pref-card" key={key}>
                  <div className="pref-card__icon">{emojiFor(key)}</div>
                  <div className="pref-card__body">
                    <div className="pref-card__key">{humanize(key)}</div>
                    <ValueView prefKey={key} value={prefs[key]} />
                  </div>
                  <button
                    className="pref-card__forget"
                    onClick={() => onForget(key)}
                    title="Forget this preference"
                  >
                    <TrashIcon size={13} />
                    Forget
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Auto-capture note */}
          <div className="prefs-note">
            <span className="prefs-note__icon">✨</span>
            <div className="prefs-note__text">
              <strong>Captured automatically.</strong> You never filled in a form —
              Hikmat PSX infers these preferences from the way you ask questions,
              updates them as you chat, and forgets anything you remove here.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
