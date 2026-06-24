// Idempotency-key generation. The backend requires request_id length >= 8;
// a UUID comfortably satisfies that and is collision-resistant.

export function newRequestId() {
  // crypto.randomUUID is available in all modern browsers (secure contexts).
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `req_${crypto.randomUUID()}`;
  }
  // Fallback for older/non-secure contexts.
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}
