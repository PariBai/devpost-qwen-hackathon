/* Welcome hero shown at the top of an empty conversation: grounding badge,
 * headline, and the four prompt-starter cards (click to send). */
import { StarIcon } from "../icons";

const STARTERS = [
  { icon: "🏦", text: "Compare HBL vs MCB" },
  { icon: "💰", text: "Best dividend yields in KSE-100" },
];

export default function WelcomeHero({ onStarter }) {
  return (
    <div className="hero">
      <div className="hero__badge">
        <StarIcon />
        Grounded in PSX data
      </div>
      <h1 className="hero__title">
        Ask anything about the <em>Pakistan market</em>.
      </h1>
      <p className="hero__lead">
        Indices, single stocks, sectors, and macro — explained plainly with the
        latest exchange figures.
      </p>
      <div className="hero__starters">
        {STARTERS.map((s) => (
          <button
            className="starter"
            key={s.text}
            onClick={() => onStarter(s.text)}
          >
            <span className="starter__icon">{s.icon}</span>
            {s.text}
          </button>
        ))}
      </div>
    </div>
  );
}
