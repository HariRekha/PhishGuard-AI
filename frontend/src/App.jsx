import React, { useEffect, useState } from "react";
import UrlForm from "./components/UrlForm";
import ResultCard from "./components/ResultCard";
import Logs from "./components/Logs";
import Train from "./components/Train";
import Login from "./components/Login";
import AdminUsers from "./components/AdminUsers";
import AdminLogs from "./components/AdminLogs";
import Register from "./components/Register";

import { getAuth, setAuth } from "./services/api";


const fallbackApi = (() => {
  if (typeof window === "undefined") return "http://localhost:8081";
  const host = window.location.hostname || "localhost";
  const protocol = window.location.protocol || "http:";
  return `${protocol}//${host}:8081`;
})();
const apiUrl = (import.meta.env.VITE_API_BASE_URL || fallbackApi).replace(/\/$/, "");

const App = () => {
  const [result, setResult] = useState(null);
  const [logsRefreshKey, setLogsRefreshKey] = useState(0);
  const [auth, setAuthState] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [page, setPage] = useState("predict");

  useEffect(() => {
    setAuthState(getAuth());
  }, []);

  const isAdmin = auth?.role === "admin";

  const pageTitle = (() => {
    switch (page) {
      case "predict":
        return "Threat Analysis";
      case "logs":
        return "Activity Logs";
      case "admin-users":
        return "User Management";
      case "admin-logs":
        return "Log Management";
      default:
        return "Dashboard";
    }
  })();

  const navItems = [
    { key: "predict", label: "Prediction", icon: "scan" },
    { key: "logs", label: "Logs", icon: "logs" },
    ...(isAdmin
      ? [
          { key: "admin-users", label: "User Management", icon: "users", admin: true },
          { key: "admin-logs", label: "Log Management", icon: "archive", admin: true },
        ]
      : []),
  ];

  const NavIcon = ({ name }) => {
    const common = {
      width: 18,
      height: 18,
      viewBox: "0 0 24 24",
      fill: "none",
      xmlns: "http://www.w3.org/2000/svg",
    };
    switch (name) {
      case "scan":
        return (
          <svg {...common}>
            <path d="M4 7V5a1 1 0 0 1 1-1h2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M20 7V5a1 1 0 0 0-1-1h-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M4 17v2a1 1 0 0 0 1 1h2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M20 17v2a1 1 0 0 1-1 1h-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M7 12h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        );
      case "logs":
        return (
          <svg {...common}>
            <path d="M8 7h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M8 12h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M8 17h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M4 7h.01M4 12h.01M4 17h.01" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        );
      case "users":
        return (
          <svg {...common}>
            <path d="M16 11a4 4 0 1 0-8 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M3 20a7 7 0 0 1 18 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        );
      case "archive":
        return (
          <svg {...common}>
            <path d="M4 7h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M6 7v13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M9 12h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div className="app">
      {!auth ? (
        <div className="auth-shell">
          <div className="auth-card">
            <div className="auth-brand">
              <div className="brand-mark" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2l7 4v6c0 5-3 9-7 10-4-1-7-5-7-10V6l7-4z" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M9 12l2 2 4-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div>
                <div className="brand-title">Phishing Intelligence</div>
                <div className="brand-subtitle">Secure access required</div>
              </div>
            </div>

            {authMode === "login" ? (
              <>
                <Login
                  onLoggedIn={(a) => {
                    setAuthState(a);
                    setLogsRefreshKey((k) => k + 1);
                    setPage("predict");
                  }}
                />
                <div className="auth-switch">
                  <button className="button ghost" onClick={() => setAuthMode("register")}>
                    Create an account
                  </button>
                </div>
              </>
            ) : (
              <Register onSwitchToLogin={() => setAuthMode("login")} />
            )}
          </div>
          <div className="auth-footnote">Backend API: {apiUrl}</div>
        </div>
      ) : (
        <div className="shell">
          <aside className="sidebar">
            <div className="sidebar-brand">
              <div className="brand-mark" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2l7 4v6c0 5-3 9-7 10-4-1-7-5-7-10V6l7-4z" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M9 12l2 2 4-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div>
                <div className="brand-title">Phishing Intelligence</div>
                <div className="brand-subtitle">SOC Console</div>
              </div>
            </div>

            <nav className="nav">
              {navItems.map((it) => (
                <button
                  key={it.key}
                  type="button"
                  className={`nav-item ${page === it.key ? "active" : ""} ${it.admin ? "admin" : ""}`}
                  onClick={() => setPage(it.key)}
                >
                  <span className="nav-icon" aria-hidden="true"><NavIcon name={it.icon} /></span>
                  <span className="nav-label">{it.label}</span>
                  {it.admin && <span className="nav-pill">ADMIN</span>}
                </button>
              ))}
            </nav>

            <div className="sidebar-footer">
              <div className="small">Connected to API</div>
              <div className="mono">{apiUrl}</div>
            </div>
          </aside>

          <div className="main">
            <div className="topbar">
              <div className="topbar-title">
                <div className="topbar-h">{pageTitle}</div>
                <div className="topbar-s">Minimal telemetry • Strong isolation</div>
              </div>

              <div className="topbar-right">
                <div className="user-chip">
                  <div className="user-chip-name">{auth.email || auth.username}</div>
                  <div className={`role-badge ${isAdmin ? "admin" : "user"}`}>{isAdmin ? "Admin" : "User"}</div>
                </div>
                <button
                  className="button ghost"
                  onClick={() => {
                    setAuth(null);
                    setAuthState(null);
                    setResult(null);
                    setLogsRefreshKey((k) => k + 1);
                    setAuthMode("login");
                  }}
                >
                  Logout
                </button>
              </div>
            </div>

            <div className="content">
              {page === "predict" && (
                <div className="grid-2">
                  <div className="stack">
                    <UrlForm
                      onResult={(r) => {
                        setResult(r);
                        setLogsRefreshKey((k) => k + 1);
                      }}
                    />
                    {isAdmin && <Train onTrained={() => setLogsRefreshKey((k) => k + 1)} />}
                  </div>
                  <div className="stack">
                    <ResultCard result={result} />
                  </div>
                </div>
              )}

              {page === "logs" && (
                <Logs
                  refreshKey={logsRefreshKey}
                  role={auth.role}
                  canDeleteOwn={!!auth.can_delete_own_logs}
                  onCleared={() => setLogsRefreshKey((k) => k + 1)}
                />
              )}

              {isAdmin && page === "admin-users" && <AdminUsers />}
              {isAdmin && page === "admin-logs" && <AdminLogs />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
