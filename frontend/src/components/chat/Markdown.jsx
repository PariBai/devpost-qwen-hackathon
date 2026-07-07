/*
 * Minimal, dependency-free markdown renderer for assistant answers.
 * Handles paragraphs, bullet/numbered lists, **bold**, *italic*, and `code`.
 * Builds React nodes (never dangerouslySetInnerHTML), so it's XSS-safe and
 * tolerant of partial text during streaming.
 */
import { Fragment } from "react";

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*|_[^_\n]+_)/g;

function parseInline(text) {
  const out = [];
  let last = 0;
  let key = 0;
  let m;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={key++}>{tok.slice(1, -1)}</code>);
    else out.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const isBullet = (l) => /^\s*[-*]\s+/.test(l);
const isNumbered = (l) => /^\s*\d+\.\s+/.test(l);
const stripMarker = (l) => l.replace(/^\s*(?:[-*]|\d+\.)\s+/, "");

export default function Markdown({ text }) {
  const blocks = text.split(/\n{2,}/);

  return (
    <div className="md">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim() !== "");
        if (lines.length === 0) return null;

        if (lines.every(isBullet)) {
          return (
            <ul key={bi}>
              {lines.map((l, i) => (
                <li key={i}>{parseInline(stripMarker(l))}</li>
              ))}
            </ul>
          );
        }
        if (lines.every(isNumbered)) {
          return (
            <ol key={bi}>
              {lines.map((l, i) => (
                <li key={i}>{parseInline(stripMarker(l))}</li>
              ))}
            </ol>
          );
        }

        return (
          <p key={bi}>
            {lines.map((l, i) => (
              <Fragment key={i}>
                {i > 0 && <br />}
                {parseInline(l)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
