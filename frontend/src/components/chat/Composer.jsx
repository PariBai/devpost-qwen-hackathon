/* Message composer: suggestion chips + an auto-growing input row.
 *
 * Behavior (per spec): Enter sends, Shift+Enter adds a newline. After sending,
 * the box clears and KEEPS FOCUS so the user can immediately type the next
 * message without clicking back into it. Send is disabled while empty. */
import { useRef, useState } from "react";
import { PaperclipIcon, MicIcon, SendIcon } from "../icons";

const MAX_H = 160;

export default function Composer({ onSend, sending }) {
  const [value, setValue] = useState("");
  const ref = useRef(null);

  const autoGrow = (el) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_H)}px`;
  };

  const focus = () => ref.current?.focus();

  const submit = (text) => {
    const msg = (text ?? value).trim();
    if (!msg || sending) return;
    onSend(msg);
    setValue("");
    // Reset height and keep the caret in the box for the next message.
    requestAnimationFrame(() => {
      if (ref.current) ref.current.style.height = "auto";
      focus();
    });
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="composer">
      <div className="composer__inner">
        <div className="composer__box">
          <span className="composer__icon" aria-hidden="true">
            <PaperclipIcon />
          </span>

          <textarea
            ref={ref}
            className="composer__input"
            rows={1}
            placeholder="Ask about a stock, index, or sector…"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              autoGrow(e.target);
            }}
            onKeyDown={onKeyDown}
          />

          <span className="composer__icon" aria-hidden="true">
            <MicIcon />
          </span>

          <button
            className="composer__send"
            onClick={() => submit()}
            disabled={!value.trim() || sending}
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        </div>

        <div className="composer__foot">
          Hikmat PSX can make mistakes — verify prices on PSX. Not financial advice.
        </div>
      </div>
    </div>
  );
}
