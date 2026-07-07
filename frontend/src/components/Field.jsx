/* Reusable form controls: a labelled text input, a password input with a
 * show/hide toggle, and a checkbox — all styled per the design tokens. */
import { useState } from "react";
import { EyeIcon, EyeOffIcon, CheckIcon } from "./icons";

export function TextField({
  label,
  labelRight,
  hint,
  id,
  className = "field",
  ...inputProps
}) {
  return (
    <div className={className}>
      {labelRight ? (
        <div className="field__label-row">
          <label className="field__label" htmlFor={id}>
            {label}
          </label>
          {labelRight}
        </div>
      ) : (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      <input id={id} className="input" {...inputProps} />
      {hint && <p className="field__hint">{hint}</p>}
    </div>
  );
}

export function PasswordField({
  label,
  labelRight,
  hint,
  id,
  className = "field",
  ...inputProps
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className={className}>
      {labelRight ? (
        <div className="field__label-row">
          <label className="field__label" htmlFor={id}>
            {label}
          </label>
          {labelRight}
        </div>
      ) : (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      <div className="input-wrap">
        <input
          id={id}
          type={visible ? "text" : "password"}
          className="input input--password"
          {...inputProps}
        />
        <button
          type="button"
          className="input-wrap__toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {hint && <p className="field__hint">{hint}</p>}
    </div>
  );
}

export function Checkbox({ checked, onChange, center = false, children }) {
  return (
    <label className={`checkbox${center ? " checkbox--center" : ""}`}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="checkbox__box">{checked && <CheckIcon size={11} />}</span>
      <span>{children}</span>
    </label>
  );
}
