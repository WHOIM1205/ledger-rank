// Typed wrappers mapping 1:1 to the backend API. Components import these, never
// the raw client. Each returns { data, status } (or throws ApiError).

import { request } from "./client.js";

// GET /health -> { status: "ok" }. Used by the health banner.
export function getHealth() {
  return request("/health");
}

// POST /transaction. status is 201 (fresh) or 200 (idempotent replay).
// Throws ApiError with code IDEMPOTENCY_CONFLICT (409) on payload mismatch,
// USER_NOT_FOUND (404), or VALIDATION_ERROR (422).
export function createTransaction(payload) {
  return request("/transaction", { method: "POST", body: payload });
}

// GET /summary/{userId}. Throws USER_NOT_FOUND (404) for unknown users.
export function getSummary(userId) {
  return request(`/summary/${encodeURIComponent(userId)}`);
}

// GET /ranking?limit=&offset= -> { rankings: [...] }.
export function getRanking({ limit = 50, offset = 0 } = {}) {
  return request(`/ranking?limit=${limit}&offset=${offset}`);
}
