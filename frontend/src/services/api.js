const fallbackBase = (() => {
  if (typeof window === "undefined") {
    return "http://localhost:8081";
  }
  const host = window.location.hostname || "localhost";
  const protocol = window.location.protocol || "http:";
  return `${protocol}//${host}:8081`;
})();
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || fallbackBase
).replace(/\/$/, "");
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || "";

const AUTH_STORAGE_KEY = "phishing_auth";

export function getAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setAuth(auth) {
  try {
    if (!auth) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  } catch {
    // ignore
  }
}

function authHeaders() {
  const auth = typeof window !== "undefined" ? getAuth() : null;
  if (auth?.token) {
    return { Authorization: `Bearer ${auth.token}` };
  }
  return {};
}

function buildError(defaultMsg, status, body) {
  const message = body?.error || `${defaultMsg}: ${status}`;
  const err = new Error(message);
  err.status = status;
  if (body && typeof body === "object") {
    err.details = body;
  }
  return err;
}

async function parseResponse(res, defaultMsg) {
  const contentType = res.headers.get("content-type") || "";
  let body = null;
  try {
    body = contentType.includes("application/json") ? await res.json() : await res.text();
  } catch (_) {
    // ignore parse errors
  }
  if (!res.ok) {
    throw buildError(defaultMsg, res.status, body && typeof body === "object" ? body : { raw: body });
  }
  if (body && typeof body === "object" && body.error) {
    // Backend may return 200 with an error envelope (defensive)
    throw buildError(defaultMsg, res.status, body);
  }
  return body;
}

// Track the current API base so we can switch after a successful fallback
let CURRENT_API_BASE = API_BASE;
function apiUrl(path) {
  return `${CURRENT_API_BASE}${path}`;
}
function computeAltLocalUrlIfApplicable(urlStr) {
  try {
    const u = new URL(urlStr);
    const isLocal = u.hostname === "localhost" || u.hostname === "127.0.0.1";
    if (!isLocal) return null;
    if (u.port === "5000" || u.port === "") {
      u.port = "8081";
      return u.toString();
    }
    if (u.port === "8081") {
      u.port = "5000";
      return u.toString();
    }
  } catch {
    // ignore
  }
  return null;
}

// Unified request helper with timeout + rich network error info + local port fallback (5000 <-> 8081)
async function request(url, options = {}, defaultMsg = "Request failed", { timeoutMs = 15000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const opts = { ...options, signal: controller.signal };

  const attempted_urls = [];
  try {
    attempted_urls.push(url);
    const res = await fetch(url, opts);
    return await parseResponse(res, defaultMsg);
  } catch (err) {
    // Try a one-time local port fallback before surfacing the error
    const alt = computeAltLocalUrlIfApplicable(url);
    if (alt) {
      try {
        attempted_urls.push(alt);
        const res2 = await fetch(alt, opts);
        const body2 = await parseResponse(res2, defaultMsg);
        // Cache the working base for future calls
        try {
          const newBase = new URL(alt).origin;
          CURRENT_API_BASE = newBase;
        } catch {
          // ignore
        }
        return body2;
      } catch {
        // fall through to enrich and throw original error
      }
    }

    const origin = typeof window !== "undefined" ? window.location.origin : "server";
    const protocol = typeof window !== "undefined" ? window.location.protocol : "";
    const isHttpsPage = protocol === "https:";
    const isHttpApi = API_BASE.startsWith("http:");
    const probable_causes = [];

    if (err.name === "AbortError") {
      probable_causes.push(
        `Request timed out after ${timeoutMs}ms`,
        "Backend is offline or slow",
        "Network connectivity issues"
      );
      const e = new Error(`${defaultMsg}: Request timed out after ${timeoutMs}ms`);
      e.status = 0;
      e.details = { timeout: true, timeoutMs, url, api_base: API_BASE, origin, method: opts.method || "GET", attempted_urls, probable_causes };
      throw e;
    }

    if (err instanceof TypeError) {
      if (isHttpsPage && isHttpApi) {
        probable_causes.push("Mixed content blocked (HTTPS page calling HTTP API)");
      }
      probable_causes.push(
        "Backend not reachable (wrong host/port or service down)",
        "CORS blocked (backend CORS origins may not include this origin)",
        "Ad-blocker/VPN/Proxy interference",
        "DNS/Firewall connectivity issues"
      );
      const e = new Error(`${defaultMsg}: Network error (Failed to fetch)`);
      e.status = 0;
      e.details = {
        network: true,
        url,
        api_base: API_BASE,
        origin,
        method: opts.method || "GET",
        headers: opts.headers || {},
        attempted_urls,
        probable_causes,
        suggestions: [
          "Open backend /health in browser to verify availability",
          "Confirm FRONTEND_ORIGINS on backend includes this origin",
          "If frontend is HTTPS, serve API over HTTPS or same origin/proxy",
        ],
      };
      throw e;
    }

    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function postPredict(payload) {
  return request(apiUrl(`/predict`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload)
  }, "Predict failed");
}

export async function getClientInfo() {
  return request(apiUrl(`/client-info`), { headers: { ...authHeaders() } }, "Failed to fetch client info");
}

export async function postLogin({ username, password }) {
  // Backward compatible: allow username, but prefer email
  const email = username;
  return request(apiUrl(`/auth/login`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username, password })
  }, "Login failed");
}

export async function postRegister({ email, password }) {
  return request(apiUrl(`/auth/register`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  }, "Register failed");
}

export async function deleteMyLogs() {
  return request(apiUrl(`/logs/mine`), {
    method: "DELETE",
    headers: { ...authHeaders() }
  }, "Delete my logs failed");
}

export async function adminSetUserPermissions(username, { can_delete_own_logs }) {
  return request(apiUrl(`/admin/users/${encodeURIComponent(username)}/permissions`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ can_delete_own_logs: !!can_delete_own_logs })
  }, "Update user permissions failed");
}

async function postTrain({ data_path = null, grid = false } = {}) {
  const headers = { "Content-Type": "application/json", ...authHeaders() };
  if (ADMIN_TOKEN) headers["X-ADMIN-TOKEN"] = ADMIN_TOKEN;
  return request(apiUrl(`/train`), {
    method: "POST",
    headers,
    body: JSON.stringify({ data_path, grid })
  }, "Train failed");
}

async function getFeaturesSchema() {
  return request(apiUrl(`/features/schema`), {}, "Failed to fetch features schema");
}

async function getLogs(limit = 25, { username = "", user_id = "" } = {}) {
  const q = new URLSearchParams();
  q.set("limit", String(limit));
  if (username) q.set("username", username);
  if (user_id !== "" && user_id !== null && user_id !== undefined) q.set("user_id", String(user_id));
  return request(apiUrl(`/logs?${q.toString()}`), { headers: { ...authHeaders() } }, "Failed to fetch logs");
}

export async function deleteLogs({ username = "", user_id = "" } = {}) {
  const q = new URLSearchParams();
  if (username) q.set("username", username);
  if (user_id !== "" && user_id !== null && user_id !== undefined) q.set("user_id", String(user_id));
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return request(apiUrl(`/logs${suffix}`), {
    method: "DELETE",
    headers: { ...authHeaders() }
  }, "Delete logs failed");
}

export async function adminListUsers() {
  return request(apiUrl(`/admin/users`), { headers: { ...authHeaders() } }, "Failed to fetch users");
}

export async function adminCreateUser({ username, password, role = "user" }) {
  return request(apiUrl(`/admin/users`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    // Prefer email-based creation, but keep username for compatibility
    body: JSON.stringify({ email: username, username, password, role })
  }, "Create user failed");
}

export async function adminSetUserRoleById(userId, role) {
  return request(apiUrl(`/admin/users/by-id/${encodeURIComponent(String(userId))}/role`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ role })
  }, "Update user role failed");
}

export async function adminGetUserLogsById(userId, limit = 30) {
  const q = new URLSearchParams();
  q.set("limit", String(limit));
  return request(
    apiUrl(`/admin/users/by-id/${encodeURIComponent(String(userId))}/logs?${q.toString()}`),
    { headers: { ...authHeaders() } },
    "Failed to fetch user logs"
  );
}

export async function adminDeleteUserLogsById(userId) {
  return request(apiUrl(`/admin/users/by-id/${encodeURIComponent(String(userId))}/logs`), {
    method: "DELETE",
    headers: { ...authHeaders() }
  }, "Delete user logs failed");
}

export async function adminSetUserRole(username, role) {
  return request(apiUrl(`/admin/users/${encodeURIComponent(username)}/role`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ role })
  }, "Update user role failed");
}

export async function adminSetUserPassword(username, password) {
  return request(apiUrl(`/admin/users/${encodeURIComponent(username)}/password`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ password })
  }, "Update user password failed");
}

export { postTrain, getFeaturesSchema, getLogs };
