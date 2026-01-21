import React, { useEffect, useState } from "react";
import { deleteLogs, deleteMyLogs, getLogs } from "../services/api";
import ConfirmDialog from "./ConfirmDialog";

const Logs = ({ refreshKey = 0, role = "user", onCleared, canDeleteOwn = false }) => {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [errorDetails, setErrorDetails] = useState(null);
  const [showErrDetails, setShowErrDetails] = useState(false);
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [confirmState, setConfirmState] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError("");
    setErrorDetails(null);
    setShowErrDetails(false);
    getLogs(30)
      .then((j) => setLogs(j))
      .catch((err) => {
        setError(String(err.message || err));
        setErrorDetails(err.details || null);
      })
      .finally(() => setLoading(false));
  }, [refreshKey]);

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h3 style={{ margin: 0 }}>Activity Logs</h3>
          <div className="small">Your secured analysis transactions. Read-only unless permitted.</div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {canDeleteOwn && role !== "admin" && (
            <button
              className="button secondary"
              disabled={clearing}
              onClick={async () => {
                setConfirmState({
                  title: "Delete my logs",
                  message: "This permanently deletes only your own logs. This action cannot be undone.",
                  confirmText: "Delete",
                  danger: true,
                  onConfirm: async () => {
                    setClearing(true);
                    setError("");
                    setErrorDetails(null);
                    setShowErrDetails(false);
                    try {
                      await deleteMyLogs();
                      onCleared?.();
                    } catch (err) {
                      setError(String(err.message || err));
                      setErrorDetails(err.details || null);
                    } finally {
                      setClearing(false);
                    }
                  },
                });
              }}
              title="Deletes only your own logged data"
            >
              {clearing ? "Deleting..." : "Delete my logs"}
            </button>
          )}

          {role === "admin" && (
            <button
              className="button danger"
              disabled={clearing}
              onClick={async () => {
                setConfirmState({
                  title: "Delete all logs (admin)",
                  message: "This permanently deletes all logs for all users. This action cannot be undone.",
                  confirmText: "Delete all",
                  danger: true,
                  onConfirm: async () => {
                    setClearing(true);
                    setError("");
                    setErrorDetails(null);
                    setShowErrDetails(false);
                    try {
                      await deleteLogs();
                      onCleared?.();
                    } catch (err) {
                      setError(String(err.message || err));
                      setErrorDetails(err.details || null);
                    } finally {
                      setClearing(false);
                    }
                  },
                });
              }}
              title="Admin only"
            >
              {clearing ? "Deleting..." : "Delete all logs"}
            </button>
          )}
        </div>
      </div>

      {loading && <div className="small">Loading...</div>}
      {error && (
        <div style={{ color: "var(--danger)", marginBottom: 8 }}>
          <div><strong>Error:</strong> {error}</div>
          {errorDetails && (
            <div style={{ marginTop: 4 }}>
              <button
                className="button secondary"
                onClick={() => setShowErrDetails((s) => !s)}
              >
                {showErrDetails ? "Hide details" : "Show details"}
              </button>
              {showErrDetails && (
                <pre
                  className="small"
                  style={{
                    marginTop: 8,
                    maxHeight: 220,
                    overflow: "auto",
                    background: "#fff4f4",
                    padding: 8,
                    borderRadius: 6,
                    border: "1px solid #f0c2c2"
                  }}
                >
                  {errorDetails.traceback
                    ? errorDetails.traceback
                    : JSON.stringify(errorDetails, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
      <div style={{ marginTop: 12 }}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 170 }}>Timestamp</th>
                <th>URL</th>
                <th style={{ width: 120 }}>Verdict</th>
                <th style={{ width: 140 }}>Probability</th>
                <th style={{ width: 220 }}>Client</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="small">No logs yet.</td>
                </tr>
              )}
              {logs.map((l) => {
                const ts = l.timestamp ? new Date(l.timestamp * 1000).toLocaleString() : "—";
                const verdict = l.prediction === 1 ? "phishing" : l.prediction === 0 ? "legitimate" : "n/a";
                const badgeClass = verdict === "phishing" ? "danger" : verdict === "legitimate" ? "safe" : "warn";
                const prob = typeof l.probability === "number" ? String(l.probability) : (l.probability ?? "—");
                return (
                  <tr key={l.id}>
                    <td className="small">{ts}</td>
                    <td>
                      <div className="logs-url" title={l.url}>{l.url}</div>
                      <div className="small">Model: {l.model_version || "—"}</div>
                    </td>
                    <td>
                      <span className={`badge ${badgeClass}`}>{verdict}</span>
                    </td>
                    <td className="small">{prob}</td>
                    <td className="small">
                      {l.device || "—"}{l.ip ? ` • ${l.ip}` : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={!!confirmState}
        title={confirmState?.title}
        message={confirmState?.message}
        confirmText={confirmState?.confirmText}
        danger={!!confirmState?.danger}
        busy={clearing}
        onCancel={() => setConfirmState(null)}
        onConfirm={async () => {
          try {
            await confirmState?.onConfirm?.();
          } finally {
            setConfirmState(null);
          }
        }}
      />
    </div>
  );
};

export default Logs;
