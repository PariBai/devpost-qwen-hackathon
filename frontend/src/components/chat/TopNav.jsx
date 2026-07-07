/* Top nav: brand mark + wordmark on the left, user avatar menu on the right.
 * (Markets/Insights/Portfolio links dropped — those pages aren't built.)
 * On narrow screens a menu button toggles the sidebar drawer. */
import { ChartGlyph, MenuIcon } from "../icons";
import UserMenu from "./UserMenu";

export default function TopNav({ onToggleSidebar }) {
  return (
    <header className="topnav">
      {onToggleSidebar && (
        <button
          className="topnav__menu-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle conversations"
        >
          <MenuIcon />
        </button>
      )}

      <div className="topnav__brand">
        <div className="topnav__mark">
          <ChartGlyph size={19} color="#fff" />
        </div>
        <div className="topnav__name">
          <span className="topnav__word">Hikmat PSX</span>
          <span className="topnav__sub">MARKET ASSISTANT</span>
        </div>
      </div>

      <div className="topnav__spacer" />
      <UserMenu />
    </header>
  );
}
