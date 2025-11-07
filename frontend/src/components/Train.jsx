import React, { useState } from "react";
import { postTrain } from "../services/api";

const Train = ({ onTrained }) => {
  const adminToken = import.meta.env.VITE_ADMIN_TOKEN || "";
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");                 // added
  const [errorDetails, setErrorDetails] = useState(null); // added
  const [showErrDetails, setShowErrDetails] = useState(false); // added

  if (!adminToken) {
    return null;
  }

  async function handleTrain() {
    if (!confirm("Trigger retraining on the backend? This may take some time.")) return;
    setLoading(true);
    setMessage("");
    setError("");
    setErrorDetails(null);
    setShowErrDetails(false);
    try {
      const res = await postTrain({ data_path: null, grid: false });
      const version = res.meta?.model_version || "unknown";
      const accuracy = typeof res.meta?.accuracy === "number" ? ` • Accuracy: ${(res.meta.accuracy * 100).toFixed(2)}%` : "";
      setMessage(`Trained. Model version: ${version}${accuracy}`);
      onTrained?.();
    } catch (err) {
      setError(String(err.message || err));
      setErrorDetails(err.details || null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h3>Admin / Training</h3>
      <p className="small">
        A training button is available because an admin token was provided to the frontend (VITE_ADMIN_TOKEN). This calls the backend <code>/train</code> endpoint with the token.
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="button" onClick={handleTrain} disabled={loading}>
          {loading ? "Training..." : "Trigger retrain"}
        </button>
        <button
          className="button secondary"
          onClick={() => {
            navigator.clipboard.writeText(adminToken);
            alert("Admin token copied to clipboard");
          }}
        >
          Copy token
        </button>
      </div>
      {message && <div style={{ marginTop: 8 }} className="small">{message}</div>}
      {error && (
        <div style={{ marginTop: 8, color: "var(--danger)" }}>
          <div><strong>Training error:</strong> {error}</div>
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
      <div style={{ marginTop: 8 }} className="small">
        Note: Avoid exposing admin tokens in production builds. Prefer server-side automation for training.
      </div>
    </div>
  );
};

export default Train;
