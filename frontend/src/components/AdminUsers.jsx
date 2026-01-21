import React, { useEffect, useMemo, useState } from "react";
import {
  adminCreateUser,
  adminDeleteUserLogsById,
  adminGetUserLogsById,
  adminListUsers,
  adminSetUserPermissions,
  adminSetUserRoleById,
} from "../services/api";
import ConfirmDialog from "./ConfirmDialog";

function formatTs(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return "—";
  }
}

const AdminUsers = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [users, setUsers] = useState([]);

  const [selectedUser, setSelectedUser] = useState(null);
  const [userLogs, setUserLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [actionBusyId, setActionBusyId] = useState(null);

  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [createLoading, setCreateLoading] = useState(false);
  const [confirmState, setConfirmState] = useState(null);

  async function reload() {
    setLoading(true);
    setError("");
    try {
      const res = await adminListUsers();
      setUsers(res?.users || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  const selectedUserLabel = useMemo(() => {
    if (!selectedUser) return "";
    return selectedUser.email || selectedUser.username || `User #${selectedUser.id}`;
  }, [selectedUser]);

  async function viewLogs(u) {
    setSelectedUser(u);
    setLogsLoading(true);
    setError("");
    try {
      const logs = await adminGetUserLogsById(u.id, 30);
      setUserLogs(Array.isArray(logs) ? logs : []);
    } catch (e) {
      setError(String(e.message || e));
      setUserLogs([]);
    } finally {
      setLogsLoading(false);
    }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          <h3 style={{ margin: 0 }}>Admin • User Management</h3>
          <div className="small">Control access and permissions. Actions are audited via logs.</div>
        </div>
        <button className="button secondary" onClick={reload} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="small" style={{ color: "var(--danger)", marginTop: 8 }}>
          {error}
        </div>
      )}

      <div className="subpanel" style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Create user</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div>
            <label className="small">Email</label>
            <input className="input" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="user@example.com" />
          </div>
          <div>
            <label className="small">Password</label>
            <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </div>
          <div>
            <label className="small">Role</label>
            <select className="input" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button
              className="button"
              disabled={createLoading}
              onClick={async () => {
                if (!newEmail.trim() || !newPassword) {
                  setError("Email and password are required");
                  return;
                }
                setCreateLoading(true);
                setError("");
                try {
                  await adminCreateUser({ username: newEmail.trim(), password: newPassword, role: newRole });
                  setNewEmail("");
                  setNewPassword("");
                  setNewRole("user");
                  await reload();
                } catch (e) {
                  setError(String(e.message || e));
                } finally {
                  setCreateLoading(false);
                }
              }}
            >
              {createLoading ? "Creating..." : "Create"}
            </button>
          </div>
        </div>
      </div>

      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Last login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && !loading && (
              <tr>
                <td colSpan={4} className="small">No users found.</td>
              </tr>
            )}
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{u.email || "—"}</div>
                  <div className="small" style={{ opacity: 0.85 }}>
                    IP: {u.last_login_ip || "—"} • Device: {u.last_login_device || "—"}
                  </div>
                </td>
                <td>
                  <span className={`badge ${u.role === "admin" ? "danger" : "safe"}`}>{u.role}</span>
                  <div className="small" style={{ marginTop: 6 }}>
                    <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={!!u.can_delete_own_logs}
                        onChange={async (e) => {
                          const next = e.target.checked;
                          setActionBusyId(u.id);
                          setError("");
                          try {
                            await adminSetUserPermissions(u.email || u.username, { can_delete_own_logs: next });
                            setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, can_delete_own_logs: next } : x)));
                          } catch (err) {
                            setError(String(err.message || err));
                          } finally {
                            setActionBusyId(null);
                          }
                        }}
                        disabled={actionBusyId === u.id}
                      />
                      Allow delete own logs
                    </label>
                  </div>
                </td>
                <td className="small">{formatTs(u.last_login_at)}</td>
                <td>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      className="button secondary"
                      onClick={() => viewLogs(u)}
                      disabled={actionBusyId === u.id}
                    >
                      View logs
                    </button>
                    <button
                      className="button secondary"
                      onClick={async () => {
                        const nextRole = u.role === "admin" ? "user" : "admin";
                        setConfirmState({
                          title: "Change user role",
                          message: `Set role to '${nextRole}' for ${u.email || u.username || `User #${u.id}`}? This affects access immediately.`,
                          confirmText: "Apply role",
                          danger: nextRole === "admin",
                          onConfirm: async () => {
                            setActionBusyId(u.id);
                            setError("");
                            try {
                              await adminSetUserRoleById(u.id, nextRole);
                              setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, role: nextRole } : x)));
                            } catch (err) {
                              setError(String(err.message || err));
                            } finally {
                              setActionBusyId(null);
                            }
                          },
                        });
                      }}
                      disabled={actionBusyId === u.id}
                    >
                      {u.role === "admin" ? "Demote" : "Promote"}
                    </button>
                    <button
                      className="button danger"
                      onClick={async () => {
                        setConfirmState({
                          title: "Delete user logs",
                          message: `Permanently delete ALL logs for ${u.email || u.username || `User #${u.id}`}? This cannot be undone.`,
                          confirmText: "Delete logs",
                          danger: true,
                          onConfirm: async () => {
                            setActionBusyId(u.id);
                            setError("");
                            try {
                              await adminDeleteUserLogsById(u.id);
                              if (selectedUser?.id === u.id) {
                                setUserLogs([]);
                              }
                            } catch (err) {
                              setError(String(err.message || err));
                            } finally {
                              setActionBusyId(null);
                            }
                          },
                        });
                      }}
                      disabled={actionBusyId === u.id}
                    >
                      Delete logs
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedUser && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div style={{ fontWeight: 600 }}>Logs for: {selectedUserLabel}</div>
            <button className="button secondary" onClick={() => viewLogs(selectedUser)} disabled={logsLoading}>
              {logsLoading ? "Loading..." : "Reload"}
            </button>
          </div>

          {logsLoading && <div className="small" style={{ marginTop: 8 }}>Loading logs...</div>}
          {!logsLoading && userLogs.length === 0 && <div className="small" style={{ marginTop: 8 }}>No logs for this user.</div>}

          <div className="logs-list" style={{ marginTop: 10 }}>
            {userLogs.map((l) => (
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
      )}

      <ConfirmDialog
        open={!!confirmState}
        title={confirmState?.title}
        message={confirmState?.message}
        confirmText={confirmState?.confirmText}
        danger={!!confirmState?.danger}
        busy={actionBusyId !== null}
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

export default AdminUsers;
