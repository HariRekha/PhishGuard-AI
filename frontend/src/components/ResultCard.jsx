import React, { useState } from "react";

function humanExplanation(features) {
  const reasons = [];
  if (!features) return "";
  if (features.suspicious_token_count > 0) reasons.push(`suspicious token(s) (${features.suspicious_token_count})`);
  if (features.ratio_digits_to_length > 0.12) reasons.push("high digit ratio");
  if (features.has_at_symbol) reasons.push("contains '@' symbol");
  if (features.count_dots >= 4) reasons.push("many dots in URL");
  if (features.has_ip_in_host) reasons.push("IP address used as host");
  if (features.ratio_special_chars_to_length > 0.12) reasons.push("many special characters");
  return reasons.length ? `Flags: ${reasons.join(", ")}` : "No strong lexical signals found.";
}

function highlightForFeature(k, v) {
  if (k === "suspicious_token_count" && v > 0) return "danger";
  if (k === "has_at_symbol" && v) return "danger";
  if (k === "has_ip_in_host" && v) return "danger";
  if (k === "ratio_digits_to_length" && v > 0.12) return "warn";
  if (k === "ratio_special_chars_to_length" && v > 0.12) return "warn";
  if ((k === "count_dots" || k === "count_hyphens") && v >= 4) return "warn";
  return "normal";
}

function getVerdictInfo(probabilityPercent, prediction, modelUnavailable) {
  if (modelUnavailable) {
    return { badgeText: "Unavailable", badgeClass: "warn", description: "No trained model is loaded." };
  }
  if (typeof probabilityPercent === "number") {
    if (probabilityPercent >= 70) {
      return { badgeText: "Danger", badgeClass: "danger", description: "High probability of phishing." };
    }
    if (probabilityPercent <= 30) {
      return { badgeText: "Safe", badgeClass: "safe", description: "Low probability of phishing." };
    }
    return { badgeText: "Caution", badgeClass: "warn", description: "Moderate probability of phishing." };
  }
  const normalized = (prediction || "").toLowerCase();
  if (normalized === "phishing") {
    return { badgeText: "Danger", badgeClass: "danger", description: "Model classified the URL as phishing." };
  }
  if (normalized === "legitimate") {
    return { badgeText: "Safe", badgeClass: "safe", description: "Model classified the URL as legitimate." };
  }
  if (normalized === "model_not_loaded") {
    return { badgeText: "Unavailable", badgeClass: "warn", description: "No trained model is loaded." };
  }
  return { badgeText: prediction || "Unknown", badgeClass: "warn", description: "Model response did not include probability." };
}

const ResultCard = ({ result }) => {
  const [showRaw, setShowRaw] = useState(false);

  if (!result) {
    return (
      <div className="card">
        <h3>Result</h3>
        <p className="small">No prediction yet — enter a URL to analyze.</p>
      </div>
    );
  }

  const features = result.features || {};
  const modelUnavailable = result.prediction === "model_not_loaded";
  const hasProbability = typeof result.probability === "number" && Number.isFinite(result.probability);
  const modelAcc = typeof result.model_accuracy === "number" ? `${(result.model_accuracy * 100).toFixed(2)}%` : null;

  if (modelUnavailable) {
    return (
      <div className="card">
        <h3>Verdict</h3>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="badge warn">Model offline</span>
          <div>
            <div className="small">
              {result.message || "No trained model is currently loaded on the backend."}
            </div>
            <div className="small">
              Train the backend (POST /train) and refresh the page once the model is ready.
            </div>
            <div className="small">Model: {result.model_version || "unknown"}</div>
            {modelAcc && <div className="small">Model accuracy: {modelAcc}</div>}
          </div>
        </div>
        {Object.keys(features).length > 0 && (
          <>
            <h4 style={{ marginTop: 16 }}>Extracted features (model offline)</h4>
            <div className="feature-grid">
              {Object.keys(features).map((k) => (
                <div key={k} className="feature">
                  <div style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}</div>
                  <div>{String(features[k])}</div>
                </div>
              ))}
            </div>
          </>
        )}
        <div style={{ marginTop: 12 }}>
          <button className="button secondary" onClick={() => setShowRaw((s) => !s)}>
            {showRaw ? "Hide" : "Show"} raw response
          </button>
        </div>
        {showRaw && (
          <pre
            style={{
              marginTop: 12,
              maxHeight: 300,
              overflow: "auto",
              background: "#f3f6ff",
              padding: 12,
              borderRadius: 8
            }}
          >
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>
    );
  }

  const phishingPercent = hasProbability ? Math.round(result.probability * 1000) / 10 : null;
  const confidencePercent = hasProbability
    ? Math.round(((result.prediction === "phishing" ? result.probability : 1 - result.probability) * 1000)) / 10
    : null;
  const verdict = getVerdictInfo(phishingPercent, result.prediction, modelUnavailable);
  const explanation = humanExplanation(features);
  const whyText = [verdict.description, explanation].filter(Boolean).join(" — ");
  const phishingDisplay = phishingPercent !== null ? `${phishingPercent}%` : "Unavailable";
  const confidenceDisplay = confidencePercent !== null ? `${confidencePercent}%` : "Unavailable";

  function copyJSON() {
    navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    alert("Result JSON copied to clipboard");
  }

  function downloadJSON() {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "prediction.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="card">
      <h3>Verdict</h3>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ fontSize: 20 }}>
          <span className={`badge ${verdict.badgeClass}`}>{verdict.badgeText}</span>
        </div>
        <div>
          <div className="small">
            Phishing likelihood: <strong>{phishingDisplay}</strong>
          </div>
          {hasProbability && (
            <div className="small">
              Model confidence: <strong>{confidenceDisplay}</strong>
            </div>
          )}
          <div className="small">Model: {result.model_version || "unknown"}</div>
          {modelAcc && <div className="small">Model accuracy: {modelAcc}</div>}
        </div>
      </div>
      <div className="result-legend" style={{ marginTop: 12 }}>
        <strong>Why:</strong> {whyText || "No additional explanation available."}
      </div>
      {modelUnavailable && (
        <div className="small" style={{ marginTop: 6 }}>
          Feature values are shown for reference only because the model is offline.
        </div>
      )}
      <h4 style={{ marginTop: 12 }}>Lexical features</h4>
      <div className="feature-grid">
        {Object.keys(features).map((k) => {
          const v = features[k];
          const level = highlightForFeature(k, v);
          return (
            <div key={k} className="feature">
              <div style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div>{String(v)}</div>
                {level !== "normal" && (
                  <div className={`badge ${level === "danger" ? "danger" : "warn"}`}>
                    {level}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button className="button secondary" onClick={() => setShowRaw((s) => !s)}>
          {showRaw ? "Hide" : "Show"} raw
        </button>
        <button className="button secondary" onClick={copyJSON}>
          Copy JSON
        </button>
        <button className="button secondary" onClick={downloadJSON}>
          Download JSON
        </button>
      </div>
      {showRaw && (
        <pre
          style={{
            marginTop: 12,
            maxHeight: 300,
            overflow: "auto",
            background: "#f3f6ff",
            padding: 12,
            borderRadius: 8
          }}
        >
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
};

export default ResultCard;
