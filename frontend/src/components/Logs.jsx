import React, { useEffect, useState } from "react";
import { getLogs } from "../services/api";

const Logs = ({ refreshKey = 0 }) => {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [errorDetails, setErrorDetails] = useState(null);
  const [showErrDetails, setShowErrDetails] = useState(false);
  const [loading, setLoading] = useState(false);

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
      <h3>Recent Logs</h3>
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
      <div className="logs-list">
        {logs.length === 0 && !loading && <div className="small">No logs yet.</div>}
        {logs.map((l) => (
          <div className="log-item" key={l.id}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div><strong>{l.url}</strong></div>
              <div className="small">{new Date(l.timestamp * 1000).toLocaleString()}</div>
            </div>
            <div className="small">
              Verdict: {l.prediction === 1 ? "phishing" : l.prediction === 0 ? "legitimate" : "n/a"} — Prob: {l.probability}
            </div>
            <div className="small">
              Device: {l.device || "—"} • IP: {l.ip || "—"} • Model: {l.model_version || "—"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Logs;
