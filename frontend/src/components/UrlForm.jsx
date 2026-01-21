import React, { useEffect, useState } from "react";
import { postPredict, postTrain, getClientInfo } from "../services/api";

function isValidUrl(s) {
  try {
    new URL(s);
    return true;
  } catch {
    return false;
  }
}

const UrlForm = ({ onResult }) => {
  const [url, setUrl] = useState("");
  const [clientInfo, setClientInfo] = useState(null);
  const [clientInfoLoading, setClientInfoLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [errorDetails, setErrorDetails] = useState(null);
  const [showErrDetails, setShowErrDetails] = useState(false);
  const [retrainLoading, setRetrainLoading] = useState(false);
  const [retrainMsg, setRetrainMsg] = useState("");

  async function loadClientInfo() {
    setClientInfoLoading(true);
    try {
      const info = await getClientInfo();
      setClientInfo(info);
    } catch (e) {
      // Client info is best-effort; do not block predictions
      console.warn("Failed to fetch client info", e);
      setClientInfo(null);
    } finally {
      setClientInfoLoading(false);
    }
  }

  useEffect(() => {
    loadClientInfo();
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setErrorDetails(null);
    setShowErrDetails(false);
    if (!url || !isValidUrl(url)) {
      setError("Please enter a valid URL (include scheme, e.g., https://)");
      return;
    }
    setLoading(true);
    try {
      const payload = {
        url,
        metadata: {
          user_agent: navigator.userAgent,
          timestamp: new Date().toISOString(),
          ui_client_info: clientInfo
        }
      };
      const res = await postPredict(payload);
      onResult(res);
    } catch (err) {
      setError(String(err.message || err));
      setErrorDetails(err.details || null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h3>Check URL</h3>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 10 }}>
          <input
            className="input"
            placeholder="https://example.com/login"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
        <div className="client-info">
          <div className="client-info-item">
            <div className="small">Device</div>
            <div className="client-info-value">
              {clientInfoLoading ? "Detecting..." : (clientInfo?.device || "Unavailable")}
            </div>
          </div>
          <div className="client-info-item">
            <div className="small">IP Address</div>
            <div className="client-info-value">
              {clientInfoLoading ? "Detecting..." : (clientInfo?.ip || "Unavailable")}
            </div>
          </div>
          <div className="client-info-actions">
            <button
              type="button"
              className="button secondary"
              onClick={loadClientInfo}
              disabled={clientInfoLoading}
              title="Refresh detected device/IP"
            >
              {clientInfoLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>
        {error && (
          <div className="error-box" style={{ marginBottom: 8 }}>
            <div><strong>Error:</strong> {error}</div>
            {errorDetails?.error_type === "ModelIncompatibleError" && (
              <div style={{ marginTop: 6 }}>
                <button
                  type="button"
                  className="button"
                  disabled={retrainLoading}
                  onClick={async () => {
                    setRetrainLoading(true);
                    setRetrainMsg("");
                    try {
                      const res = await postTrain({ data_path: null, grid: false });
                      const version = res?.meta?.model_version || "unknown";
                      setRetrainMsg(`Retrained successfully. Model version: ${version}. Try your URL again.`);
                    } catch (e) {
                      setRetrainMsg(`Retrain failed: ${String(e.message || e)}`);
                    } finally {
                      setRetrainLoading(false);
                    }
                  }}
                >
                  {retrainLoading ? "Retraining..." : "Retrain backend model"}
                </button>
                {retrainMsg && <div className="small" style={{ marginTop: 6 }}>{retrainMsg}</div>}
                <div className="small" style={{ marginTop: 4 }}>
                  Note: Admin token must be configured in the frontend (VITE_ADMIN_TOKEN) to authorize training.
                </div>
              </div>
            )}
            {errorDetails && (
              <div style={{ marginTop: 6 }}>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setShowErrDetails((s) => !s)}
                >
                  {showErrDetails ? "Hide details" : "Show details"}
                </button>
                {showErrDetails && (
                  <pre
                    className="error-pre"
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
        <div style={{ display: "flex", gap: 8 }}>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "Checking..." : "Detect"}
          </button>
          <button
            className="button secondary"
            type="button"
            onClick={() => {
              setUrl("");
              setError("");
              setErrorDetails(null);
              setShowErrDetails(false);
            }}
          >
            Reset
          </button>
        </div>
      </form>
      <p className="small" style={{ marginTop: 10 }}>
        Tip: This tool only analyzes the URL string (lexical features). It will{" "}
        <strong>not</strong> visit the URL or perform network requests to the target
        domain.
      </p>
    </div>
  );
};

export default UrlForm;
