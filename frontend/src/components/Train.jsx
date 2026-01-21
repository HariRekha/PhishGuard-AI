import React, { useState } from "react";
import { postTrain } from "../services/api";
import ConfirmDialog from "./ConfirmDialog";

const Train = ({ onTrained }) => {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");                 // added
  const [errorDetails, setErrorDetails] = useState(null); // added
  const [showErrDetails, setShowErrDetails] = useState(false); // added
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function handleTrain() {
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
      <h3>Admin • Model Retraining</h3>
      <p className="small">Triggers retraining on the backend. Use only when needed.</p>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="button secondary" onClick={() => setConfirmOpen(true)} disabled={loading}>
          {loading ? "Training..." : "Trigger retrain"}
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
        Note: For production, replace demo credentials with real authentication.
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Trigger model retraining"
        message="This will retrain the model on the backend and may take time. Continue?"
        confirmText="Retrain"
        danger={false}
        busy={loading}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={async () => {
          setConfirmOpen(false);
          await handleTrain();
        }}
      />
    </div>
  );
};

export default Train;
