/* Chat column header: title + "Market open" pill + delayed-data note. */
export default function ChatHeader() {
  return (
    <div className="chathead">
      <div className="chathead__left">
        <span className="chathead__title">Market Assistant</span>
        <span className="pill-open">
          <span className="pill-open__dot" />
          Market open
        </span>
      </div>
      <span className="chathead__meta">Delayed 15m · PSX</span>
    </div>
  );
}
