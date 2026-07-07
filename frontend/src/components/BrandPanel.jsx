/*
 * The gradient brand panel shown on the left of every auth screen.
 * Logo + wordmark, hero copy, a KSE-100 mini quote card, and the perks list.
 * Collapses on narrow viewports (see auth.css).
 */
import { ChartGlyph, CheckIcon } from "./icons";

const PERKS = [
  "Real-time indices, quotes & sectors",
  "Plain-language market analysis",
  "Delayed data · not financial advice",
];

export default function BrandPanel() {
  return (
    <div className="brand-panel">
      <div className="brand-panel__glow" />

      {/* Logo + wordmark */}
      <div className="brand-panel__inner brand-logo">
        <div className="brand-logo__mark">
          <ChartGlyph />
        </div>
        <div className="brand-logo__name">
          <span className="brand-logo__word">Hikmat PSX</span>
          <span className="brand-logo__sub">MARKET ASSISTANT</span>
        </div>
      </div>

      {/* Hero + mini quote card */}
      <div className="brand-hero">
        <h1 className="brand-hero__title">Ask anything about the Pakistan market.</h1>
        <p className="brand-hero__lead">
          Indices, single stocks, sectors and macro — explained plainly with the
          latest exchange figures.
        </p>

        <div className="brand-quote">
          <div className="brand-quote__row">
            <span className="brand-quote__sym">KSE-100</span>
            <span className="brand-quote__chg">▲ +0.66%</span>
          </div>
          <div className="brand-quote__val">78,450.32</div>
          <svg
            className="brand-quote__spark"
            viewBox="0 0 320 48"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              d="M0,40 L27,34 L53,37 L80,28 L107,31 L133,22 L160,25 L187,17 L213,20 L240,12 L267,15 L293,7 L320,4"
              fill="none"
              stroke="#7CE0B0"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      {/* Perks */}
      <div className="brand-perks">
        {PERKS.map((perk) => (
          <div className="brand-perk" key={perk}>
            <span className="brand-perk__tick">
              <CheckIcon />
            </span>
            {perk}
          </div>
        ))}
      </div>
    </div>
  );
}
