// The single place that knows how to talk HTTP to the backend.
// Components never call fetch directly — they go through endpoints.js, which
// uses this wrapper. All error handling normalizes the backend's uniform
// envelope: { "error": { code, message, details } }.

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

// Normalized error thrown by request(). Carries the backend envelope fields so
// the UI always reads the same shape regardless of which endpoint failed.
export class ApiError extends Error {
  constructor({ status, code, message, details }) {
    super(message || "Request failed");
    this.name = "ApiError";
    this.status = status;
    this.code = code || "UNKNOWN";
    this.details = details || {};
  }
}

// Core request helper. Returns { data, status } on success so callers can
// distinguish 201 (fresh) from 200 (idempotent replay). Throws ApiError on any
// non-2xx response or network failure.
export async function request(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    // Backend unreachable / CORS / DNS — surface as a typed error.
    throw new ApiError({
      status: 0,
      code: "NETWORK_ERROR",
      message: "Cannot reach the backend.",
      details: { cause: String(networkErr) },
    });
  }

  // Some responses (e.g. health) may not be JSON; guard parsing.
  let payload = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text };
    }
  }

  if (!res.ok) {
    const envelope = payload && payload.error ? payload.error : {};
    throw new ApiError({
      status: res.status,
      code: envelope.code,
      message: envelope.message || `HTTP ${res.status}`,
      details: envelope.details,
    });
  }

  return { data: payload, status: res.status };
}

export { BASE_URL };
