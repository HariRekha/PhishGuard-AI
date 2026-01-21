import React, { useEffect, useMemo, useState } from "react";
import { adminDeleteUserLogsById, adminListUsers, getLogs } from "../services/api";
import ConfirmDialog from "./ConfirmDialog";

function formatTs(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return "—";
  }
}

const AdminLogs = () => {
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("all");
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmState, setConfirmState] = useState(null);

  const selectedUser = useMemo(() => {
    if (selectedUserId === "all") return null;
    const id = Number(selectedUserId);
    return users.find((u) => u.id === id) || null;
  }, [selectedUserId, users]);

  async function loadUsers() {
    const res = await adminListUsers();
    setUsers(res?.users || []);
  }

  async function loadLogs(nextUserId = selectedUserId) {
    setLoading(true);
    setError("");
    try {
      if (nextUserId === "all") {
        const all = await getLogs(50);
        setLogs(Array.isArray(all) ? all : []);
      } else {
        const id = Number(nextUserId);
        const byUser = await getLogs(50, { user_id: id });
        setLogs(Array.isArray(byUser) ? byUser : []);
      }
    } catch (e) {
      setError(String(e.message || e));
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        await loadUsers();
        await loadLogs("all");
      } catch (e) {
        setError(String(e.message || e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          <h3 style={{ margin: 0 }}>Admin • Log Management</h3>
          <div className="small">Filter by user and perform scoped deletions with confirmation.</div>
        </div>
        <button className="button secondary" onClick={() => loadLogs(selectedUserId)} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 10, alignItems: "center" }}>
        <div style={{ minWidth: 260 }}>
          <label className="small">Filter by user</label>
          <select
            className="input"
            value={selectedUserId}
            onChange={async (e) => {
              const v = e.target.value;
              setSelectedUserId(v);
              await loadLogs(v);
            }}
          >
            <option value="all">All users</option>
            {users.map((u) => (
              <option key={u.id} value={String(u.id)}>
                {u.email} ({u.role})
              </option>
            ))}
          </select>
        </div>

        {selectedUser && (
          <button
            className="button danger"
            disabled={busy}
            onClick={async () => {
              setConfirmState({
                title: "Delete logs for selected user",
                message: `Permanently delete ALL logs for ${selectedUser.email}? This cannot be undone.`,
                confirmText: "Delete logs",
                danger: true,
                onConfirm: async () => {
                  setBusy(true);
                  setError("");
                  try {
                    await adminDeleteUserLogsById(selectedUser.id);
                    await loadLogs(selectedUserId);
                  } catch (e) {
                    setError(String(e.message || e));
                  } finally {
                    setBusy(false);
                  }
                },
              });
            }}
          >
            {busy ? "Deleting..." : "Delete logs for selected user"}
          </button>
        )}
      </div>

      {error && <div className="small" style={{ color: "var(--danger)", marginTop: 8 }}>{error}</div>}

      <div style={{ marginTop: 12 }}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 170 }}>Timestamp</th>
                <th>URL</th>
                <th style={{ width: 140 }}>User</th>
                <th style={{ width: 120 }}>Verdict</th>
                <th style={{ width: 220 }}>Client</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={5} className="small">Loading...</td>
                </tr>
              )}
              {!loading && logs.length === 0 && (
                <tr>
                  <td colSpan={5} className="small">No logs.</td>
                </tr>
              )}
              {!loading && logs.map((l) => {
                const verdict = l.prediction === 1 ? "phishing" : l.prediction === 0 ? "legitimate" : "n/a";
                const badgeClass = verdict === "phishing" ? "danger" : verdict === "legitimate" ? "safe" : "warn";
                return (
                  <tr key={l.id}>
                    <td className="small">{formatTs(l.timestamp)}</td>
                    <td>
                      <div className="logs-url" title={l.url}>{l.url}</div>
                      <div className="small">Model: {l.model_version || "—"}</div>
                    </td>
                    <td className="small">{l.owner_username || "—"}</td>
                    <td><span className={`badge ${badgeClass}`}>{verdict}</span></td>
                    <td className="small">{l.device || "—"}{l.ip ? ` • ${l.ip}` : ""}</td>
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
        busy={busy}
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

export default AdminLogs;
