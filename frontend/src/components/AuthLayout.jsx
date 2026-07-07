/*
 * Split-panel shell for the auth screens: brand panel + a form panel whose
 * card is vertically centered. Optional top-right slot and a Back button.
 */
import BrandPanel from "./BrandPanel";
import { BackIcon } from "./icons";

export default function AuthLayout({ topRight, onBack, children }) {
  return (
    <div className="auth-shell">
      <BrandPanel />
      <div className="form-panel">
        <div className="form-panel__top">{topRight}</div>
        <div className="form-panel__body">
          <div className="form-card">
            {onBack && (
              <button type="button" className="form-back" onClick={onBack}>
                <BackIcon />
                Back
              </button>
            )}
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
