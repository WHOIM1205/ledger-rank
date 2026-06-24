// Shared formatting helpers (money + dates). Used everywhere so display is
// consistent and cents<->dollars conversion lives in one place.

// Integer cents -> "$25.99".
export function formatMoney(cents) {
  if (cents === null || cents === undefined) return "—";
  const dollars = cents / 100;
  return dollars.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
}

// Dollars string/number -> integer cents (rounded). Returns null if invalid.
export function dollarsToCents(value) {
  if (value === "" || value === null || value === undefined) return null;
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return Math.round(num * 100);
}

// Backend stores UTC (naive). Display as a readable local string.
export function formatDate(iso) {
  if (!iso) return "—";
  // Treat naive timestamps as UTC by appending Z when no offset is present.
  const normalized = /[zZ]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
