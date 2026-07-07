/* Scrolling market ticker (marquee). Static data for now — the user will wire a
 * live feed later. The row is duplicated so the CSS marquee loops seamlessly. */

const TICKER_ROW = [
  { sym: "KSE-100", val: "78,450.32", chg: "+0.66%", up: true },
  { sym: "KMI-30", val: "129,204.8", chg: "+0.71%", up: true },
  { sym: "ALLSHR", val: "49,118.5", chg: "+0.48%", up: true },
  { sym: "USD/PKR", val: "278.35", chg: "-0.12%", up: false },
  { sym: "OGDC", val: "178.45", chg: "+1.83%", up: true },
  { sym: "LUCK", val: "1,042.10", chg: "-0.34%", up: false },
  { sym: "ENGRO", val: "318.75", chg: "+0.92%", up: true },
  { sym: "HBL", val: "132.60", chg: "+1.10%", up: true },
];

const UP = "#7CE0B0";
const DOWN = "#F3A3A3";

export default function Ticker() {
  const loop = [...TICKER_ROW, ...TICKER_ROW];
  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker__track">
        {loop.map((t, i) => (
          <span className="ticker__item" key={`${t.sym}-${i}`}>
            <span className="ticker__sym">{t.sym}</span>
            <span className="ticker__val">{t.val}</span>
            <span className="ticker__chg" style={{ color: t.up ? UP : DOWN }}>
              {t.chg}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
