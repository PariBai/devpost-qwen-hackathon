/* Renders one message: a right-aligned user bubble, or an assistant row with
 * the brand avatar + markdown body. While an assistant reply is streaming it
 * shows the typing dots (empty) or a blinking caret (mid-text). */
import { ChartGlyph } from "../icons";
import Markdown from "./Markdown";

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
