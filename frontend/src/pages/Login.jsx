/* Log-in screen. Authenticates by email + password, stores the token, then
 * routes into the chat. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { TextField, PasswordField, Checkbox } from "../components/Field";
import { useAuth } from "../context/AuthContext";
import { login } from "../api/auth";

export default function Login() {
  const navigate = useNavigate();
  const { signIn } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [keep, setKeep] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await login({ email: email.trim(), password });
      signIn(res);
      navigate("/chat", { replace: true });
    } catch (err) {
      setError(err.message || "Could not log in.");
    } finally {
      setBusy(false);
    }
  }

  const topRight = (
    <span>
      New here? <a onClick={() => navigate("/signup")}>Create an account</a>
    </span>
  );

  return (
    <AuthLayout topRight={topRight} onBack={() => navigate("/")}>
      <h2 className="form-title form-title--sm">Welcome back</h2>
      <p className="form-lead">Log in to your Hikmat PSX account.</p>

      {error && <div className="form-error">{error}</div>}

      <form onSubmit={onSubmit}>
        <TextField
          id="login-email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <PasswordField
          id="login-password"
          label="Password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="field mb-20"
          labelRight={<a className="field__link">Forgot?</a>}
        />

        <div className="mb-24">
          <Checkbox center checked={keep} onChange={(e) => setKeep(e.target.checked)}>
            Keep me signed in
          </Checkbox>
        </div>

        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>

      <p className="form-foot">
        New to Hikmat PSX?{" "}
        <a onClick={() => navigate("/signup")}>Create an account</a>
      </p>
    </AuthLayout>
  );
}
