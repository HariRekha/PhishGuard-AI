import React, { useMemo, useState } from "react";
import { postRegister } from "../services/api";

const Register = ({ onSwitchToLogin }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const validation = useMemo(() => {
    const e = (email || "").trim().toLowerCase();
    if (!e) return "Email is required";
    if (!e.includes("@")) return "Enter a valid email";
    if (!password) return "Password is required";
    if (password.length < 8) return "Password must be at least 8 characters";
    if (password !== confirm) return "Passwords do not match";
    return "";
  }, [email, password, confirm]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (validation) {
      setError(validation);
      return;
    }

    setLoading(true);
    try {
      await postRegister({ email: email.trim().toLowerCase(), password });
      setSuccess("Account created. You can now log in.");
      setPassword("");
      setConfirm("");
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-panel">
      <div className="auth-title">Create account</div>
      <div className="small">Register to access protected analysis and secured logs.</div>
      <form onSubmit={handleSubmit} className="auth-form">
        <div className="field">
          <label className="small">Email</label>
          <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </div>
        <div className="field">
          <label className="small">Password</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </div>
        <div className="field">
          <label className="small">Confirm password</label>
          <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
        </div>

        {error && <div className="small" style={{ color: "var(--danger)" }}>{error}</div>}
        {success && <div className="small" style={{ color: "rgba(34, 197, 94, 0.95)" }}>{success}</div>}

        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "Creating..." : "Register"}
          </button>
          <button type="button" className="button ghost" onClick={() => onSwitchToLogin?.()}>
            Back to login
          </button>
        </div>
      </form>
    </div>
  );
};

export default Register;
