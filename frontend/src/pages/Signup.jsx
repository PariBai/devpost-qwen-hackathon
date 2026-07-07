/* Sign-up screen. Collects full name + email + password, creates the account,
 * stores the token, then routes into the chat. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { TextField, PasswordField, Checkbox } from "../components/Field";
import { useAuth } from "../context/AuthContext";
import { signup } from "../api/auth";

export default function Signup() {
  const navigate = useNavigate();
  const { signIn } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");

    if (!agree) {
      setError("Please accept the Terms and Privacy Policy to continue.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setBusy(true);
    try {
      const res = await signup({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
      });
      signIn(res);
      navigate("/chat", { replace: true });
    } catch (err) {
      setError(err.message || "Could not create your account.");
    } finally {
      setBusy(false);
    }
  }

  const topRight = (
    <span>
      Already have an account? <a onClick={() => navigate("/login")}>Log in</a>
    </span>
  );

  return (
    <AuthLayout topRight={topRight} onBack={() => navigate("/")}>
      <h2 className="form-title form-title--sm">Create your account</h2>
      <p className="form-lead">Start exploring the Pakistan market with Hikmat PSX.</p>

      {error && <div className="form-error">{error}</div>}

      <form onSubmit={onSubmit}>
        <TextField
          id="signup-name"
          label="Full name"
          type="text"
          autoComplete="name"
          placeholder="Ayesha Khan"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
        />

        <TextField
          id="signup-email"
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <PasswordField
          id="signup-password"
          label="Password"
          autoComplete="new-password"
          placeholder="Create a password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          hint="At least 6 characters."
        />

        <div className="mb-24" style={{ marginTop: 18 }}>
          <Checkbox checked={agree} onChange={(e) => setAgree(e.target.checked)}>
            I agree to Hikmat PSX's <a>Terms</a> and <a>Privacy Policy</a>. Hikmat
            PSX provides information, not financial advice.
          </Checkbox>
        </div>

        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="form-foot">
        Already have an account? <a onClick={() => navigate("/login")}>Log in</a>
      </p>
    </AuthLayout>
  );
}
