import React, { useState } from "react";
import { postLogin, setAuth } from "../services/api";

const Login = ({ onLoggedIn }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await postLogin({ username: email, password });
      const auth = {
        token: res.token,
        role: res.role,
        user_id: res.user_id,
        email: res.email,
        username: res.username,
        can_delete_own_logs: !!res.can_delete_own_logs,
      };
      setAuth(auth);
      onLoggedIn?.(auth);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-panel">
      <div className="auth-title">Sign in</div>
      <div className="small">Enter your credentials to access secured logs and analysis.</div>
      <form onSubmit={handleSubmit} className="auth-form">
        <div className="field">
          <label className="small">Email</label>
          <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        </div>
        <div className="field">
          <label className="small">Password</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </div>
        {error && <div className="small" style={{ color: "var(--danger)" }}>{error}</div>}
        <button className="button" type="submit" disabled={loading}>
          {loading ? "Authenticating..." : "Login"}
        </button>
      </form>
    </div>
  );
};

export default Login;
