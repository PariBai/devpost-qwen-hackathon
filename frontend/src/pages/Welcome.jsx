/* Welcome / landing screen — entry point with Create-account and Log-in CTAs. */
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { ChartGlyph } from "../components/icons";

export default function Welcome() {
  const navigate = useNavigate();

  return (
    <AuthLayout>
      <div className="form-icon">
        <ChartGlyph size={24} color="#fff" />
      </div>

      <h2 className="form-title">Welcome to Hikmat PSX</h2>
      <p className="form-lead">
        Your AI copilot for the Pakistan Stock Exchange. Create an account or sign
        in to pick up your market conversations.
      </p>

      <button
        className="btn btn--primary"
        onClick={() => navigate("/signup")}
      >
        Create free account
      </button>
      <button className="btn btn--ghost" onClick={() => navigate("/login")}>
        Log in
      </button>

      <p className="form-terms">
        By continuing you agree to Hikmat PSX's <a>Terms</a> and{" "}
        <a>Privacy Policy</a>.
      </p>
    </AuthLayout>
  );
}
