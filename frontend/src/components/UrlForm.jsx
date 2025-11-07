import React, { useState } from "react";
import { postPredict, getPublicIP, postTrain } from "../services/api";

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
  const [device, setDevice] = useState(navigator.platform || "");
  const [ip, setIp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [errorDetails, setErrorDetails] = useState(null);
  const [showErrDetails, setShowErrDetails] = useState(false);
  const [autoIpEnabled, setAutoIpEnabled] = useState(false);
  const [retrainLoading, setRetrainLoading] = useState(false);
  const [retrainMsg, setRetrainMsg] = useState("");

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
      let ipToSend = ip;
      if (autoIpEnabled && !ip) {
        try {
          ipToSend = await getPublicIP();
        } catch (err) {
          console.warn("Auto IP failed", err);
        }
      }
      const payload = {
        url,
        device,
        ip: ipToSend,
        metadata: {
          user_agent: navigator.userAgent,
          timestamp: new Date().toISOString()
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
        <div style={{ marginBottom: 10 }}>
          <label className="small">Device (optional)</label>
          <input
            className="input"
            value={device}
            onChange={(e) => setDevice(e.target.value)}
          />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label className="small">IP (optional)</label>
          <div className="form-row">
            <input
              className="input"
              value={ip}
              onChange={(e) => setIp(e.target.value)}
              placeholder="1.2.3.4"
            />
            <button
              type="button"
              className="button secondary"
              onClick={() => setIp("")}
            >
              Clear
            </button>
          </div>
        </div>
        <div
          style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center" }}
        >
          <label className="small">
            <input
              type="checkbox"
              checked={autoIpEnabled}
              onChange={(e) => setAutoIpEnabled(e.target.checked)}
            />{" "}
            Auto fetch public IP (optional)
          </label>
        </div>
        {error && (
          <div style={{ color: "var(--danger)", marginBottom: 8 }}>
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
                    style={{
                      marginTop: 8,
                      maxHeight: 200,
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
        <div style={{ display: "flex", gap: 8 }}>
          <button className="button" type="submit" disabled={loading}>
            {loading ? "Checking..." : "Detect"}
          </button>
          <button
            className="button secondary"
            type="button"
            onClick={() => {
              setUrl("");
              setIp("");
              setDevice(navigator.platform || "");
              setAutoIpEnabled(false);
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
