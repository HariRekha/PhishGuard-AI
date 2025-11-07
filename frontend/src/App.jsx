import React, { useState } from "react";
import UrlForm from "./components/UrlForm";
import ResultCard from "./components/ResultCard";
import Logs from "./components/Logs";
import Train from "./components/Train";
import './App.css'

const fallbackApi = (() => {
  if (typeof window === "undefined") return "http://localhost:5000";
  const host = window.location.hostname || "localhost";
  const protocol = window.location.protocol || "http:";
  return `${protocol}//${host}:5000`;
})();
const apiUrl = (import.meta.env.VITE_API_BASE_URL || fallbackApi).replace(/\/$/, "");

const App = () => {
  const [result, setResult] = useState(null);
  const [logsRefreshKey, setLogsRefreshKey] = useState(0);

  return (
    <div className="app">
      <header className="header">
        <h1>Phishing URL Detector</h1>
        <p className="subtitle">Enter a URL and see lexical features + verdict</p>
      </header>
      <main className="container">
        <section className="left">
          <UrlForm
            onResult={(r) => {
              setResult(r);
              setLogsRefreshKey((k) => k + 1);
            }}
          />
          <Train onTrained={() => setLogsRefreshKey((k) => k + 1)} />
          <Logs refreshKey={logsRefreshKey} />
        </section>
        <aside className="right">
          <ResultCard result={result} />
        </aside>
      </main>
      <footer className="footer">
        <small>Frontend: Vite + React. Backend API: {apiUrl}</small>
      </footer>
    </div>
  );
};

export default App;
