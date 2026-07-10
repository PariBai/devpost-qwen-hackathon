/* Renders one message: a right-aligned user bubble, an assistant row with the
 * brand avatar + markdown body, or a "memory updated" feed card. While an
 * assistant reply is streaming it shows typing dots (empty) or a caret. */
import { ChartGlyph } from "../icons";
import Markdown from "./Markdown";

// --- compact preference formatting for the memory feed ---
function humanizeKey(k) {
  const s = String(k).replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function shortValue(v) {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v !== "object") return String(v);
  if (Array.isArray(v)) return v.map(shortValue).filter(Boolean).join(", ");
  return Object.values(v).map(shortValue).filter(Boolean).join(", ");
}

function MemoryFeed({ ops }) {
  return (
    <div className="mem-feed">
      <div className="mem-feed__head">
        <span className="mem-feed__spark">🧠</span> Memory updated
      </div>
      {ops.map((op, i) => {
        const remembered = op.action === "remembered";
        const val = shortValue(op.value);
        return (
          <div className="mem-op" key={i}>
            <span className={`mem-op__badge mem-op__badge--${op.action}`}>
              {remembered ? "Remembered" : "Forgot"}
            </span>
            <div className="mem-op__body">
              <div className="mem-op__kv">
                {humanizeKey(op.key)}
                {remembered && val ? (
                  <>
                    {" → "}
                    <strong>{val}</strong>
                  </>
                ) : null}
              </div>
              {op.reason && <div className="mem-op__reason">{op.reason}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AssistantAvatar() {
  return (
    <div className="msg-assistant__avatar">
      <ChartGlyph size={16} color="#fff" />
    </div>
  );
}

function TypingDots() {
  return (
    <div className="typing__bubble">
      <span className="typing__dot" />
      <span className="typing__dot" />
      <span className="typing__dot" />
    </div>
  );
}

export default function Message({ message }) {
  if (message.role === "user") {
    return (
      <div className="msg-user">
        <div className="msg-user__bubble">{message.text}</div>
      </div>
    );
  }

  if (message.role === "memory") {
    return <MemoryFeed ops={message.ops} />;
  }

  const empty = !message.text;

  // Streaming with no text yet -> typing indicator row.
  if (empty && message.streaming) {
    return (
      <div className="typing">
        <AssistantAvatar />
        <TypingDots />
      </div>
    );
  }

  return (
    <div className="msg-assistant">
      <AssistantAvatar />
      <div className="msg-assistant__body">
        <Markdown text={message.text} />
        {message.streaming && <span className="caret" />}
        {message.error && (
          <div className="msg-assistant__error">{message.error}</div>
        )}
      </div>
    </div>
  );
}
