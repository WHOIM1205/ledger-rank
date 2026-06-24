// Transaction creation panel. Demonstrates idempotency three ways:
//   1. Submit New Transaction      -> fresh request_id -> 201
//   2. Retry Same request_id        -> same id + same payload -> 200 duplicate
//   3. Replay With Different Amount -> same id + changed amount -> 409 conflict
//
// Owns its own form state (useState) and drives the create call via useApi.

import { useState } from "react";
import { useApi } from "../../hooks/useApi.js";
import { createTransaction } from "../../api/endpoints.js";
import { newRequestId } from "../../api/requestId.js";
import { dollarsToCents } from "../../lib/format.js";
import Card from "../ui/Card.jsx";
import ErrorBanner from "../ui/ErrorBanner.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";
import Loading from "../ui/Loading.jsx";

const SEED_HINT = "Seeded ids: u_1, u_2, u_3, u_4, u_5";

export default function TransactionForm({ onTransactionApplied }) {
  const [userId, setUserId] = useState("u_1");
  const [amount, setAmount] = useState("25.99");
  const [currency, setCurrency] = useState("USD");
  const [type, setType] = useState("credit");

  // Tracks the last created transaction so retry/conflict can reuse its id.
  const [lastRequestId, setLastRequestId] = useState(null);

  const { data, status, error, loading, run, reset } =
    useApi(createTransaction);

  const cents = dollarsToCents(amount);
  const amountValid = cents !== null && cents > 0;

  async function submit(requestId, amountCents) {
    const result = await run({
      request_id: requestId,
      user_id: userId.trim(),
      amount_cents: amountCents,
      currency,
      type,
    });
    if (result && result.status >= 200 && result.status < 300) {
      // Refresh summary + leaderboard after any successful apply/replay.
      onTransactionApplied?.();
    }
    return result;
  }

  // 1. Fresh transaction with a brand-new request_id.
  async function handleNew() {
    if (!amountValid) return;
    const rid = newRequestId();
    setLastRequestId(rid);
    await submit(rid, cents);
  }

  // 2. Retry the exact same request_id + same payload -> idempotent replay (200).
  async function handleRetry() {
    if (!lastRequestId || !amountValid) return;
    await submit(lastRequestId, cents);
  }

  // 3. Reuse the same request_id but with a DIFFERENT amount -> 409 conflict.
  async function handleConflict() {
    if (!lastRequestId) return;
    const conflictingCents = (cents || 100) + 100; // guaranteed different
    await submit(lastRequestId, conflictingCents);
  }

  return (
    <Card
      title="Create Transaction"
      subtitle="Demonstrates idempotency, replay, and conflict detection."
    >
      <div className="form">
        <label className="field">
          <span className="field__label">User ID</span>
          <input
            className="field__input"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="u_1"
          />
          <span className="field__hint">{SEED_HINT}</span>
        </label>

        <div className="form__row">
          <label className="field">
            <span className="field__label">Amount</span>
            <input
              className="field__input"
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            {!amountValid && (
              <span className="field__hint field__hint--warn">
                Enter an amount greater than 0.
              </span>
            )}
          </label>

          <label className="field">
            <span className="field__label">Currency</span>
            <input
              className="field__input"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              maxLength={3}
            />
          </label>

          <label className="field">
            <span className="field__label">Type</span>
            <select
              className="field__input"
              value={type}
              onChange={(e) => setType(e.target.value)}
            >
              <option value="credit">credit</option>
              <option value="debit">debit</option>
            </select>
          </label>
        </div>

        <div className="form__actions">
          <button
            className="btn btn--primary"
            onClick={handleNew}
            disabled={loading || !amountValid}
          >
            Submit New Transaction
          </button>
          <button
            className="btn"
            onClick={handleRetry}
            disabled={loading || !lastRequestId || !amountValid}
            title="Resends the same request_id with the same payload"
          >
            Retry Same request_id
          </button>
          <button
            className="btn btn--warn"
            onClick={handleConflict}
            disabled={loading || !lastRequestId}
            title="Reuses the same request_id with a different amount"
          >
            Replay With Different Amount
          </button>
        </div>

        {lastRequestId && (
          <p className="form__meta">
            Active request_id: <code>{lastRequestId}</code>
          </p>
        )}

        {loading && <Loading label="Submitting…" />}

        {!loading && status !== null && !error && (
          <div className="result">
            <StatusBadge status={status} duplicate={data?.duplicate} />
            <div className="result__grid">
              <span>Transaction #{data?.id}</span>
              <span>request_id: {data?.request_id}</span>
              <span>amount_cents: {data?.amount_cents}</span>
              <span>currency: {data?.currency}</span>
              <span>duplicate: {String(data?.duplicate)}</span>
            </div>
          </div>
        )}

        {!loading && error && (
          <ErrorBanner
            error={error}
            title={
              error.code === "IDEMPOTENCY_CONFLICT"
                ? "Conflict — request_id reused with a different payload"
                : "Request failed"
            }
          />
        )}

        {(status !== null || error) && (
          <button className="btn btn--ghost" onClick={reset}>
            Clear result
          </button>
        )}
      </div>
    </Card>
  );
}
