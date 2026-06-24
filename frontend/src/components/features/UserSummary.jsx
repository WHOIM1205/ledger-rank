// Per-user summary panel. Looks up GET /summary/{userId} and renders the
// aggregate. Re-fetches whenever refreshKey changes (after a transaction) or
// the looked-up user changes.

import { useEffect, useState } from "react";
import { useApi } from "../../hooks/useApi.js";
import { getSummary } from "../../api/endpoints.js";
import { formatMoney, formatDate } from "../../lib/format.js";
import Card from "../ui/Card.jsx";
import ErrorBanner from "../ui/ErrorBanner.jsx";
import Loading from "../ui/Loading.jsx";
import EmptyState from "../ui/EmptyState.jsx";

export default function UserSummary({ refreshKey }) {
  const [userId, setUserId] = useState("u_1");
  const [activeUserId, setActiveUserId] = useState("u_1");
  const { data, error, loading, run } = useApi(getSummary);

  // Re-fetch when the active user or the global refreshKey changes.
  useEffect(() => {
    if (activeUserId) run(activeUserId);
  }, [activeUserId, refreshKey, run]);

  function handleLookup(e) {
    e.preventDefault();
    setActiveUserId(userId.trim());
  }

  return (
    <Card title="User Summary" subtitle="O(1) aggregate read from user_stats.">
      <form className="form__inline" onSubmit={handleLookup}>
        <input
          className="field__input"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="u_1"
          aria-label="User ID"
        />
        <button className="btn btn--primary" type="submit" disabled={loading}>
          Look up
        </button>
      </form>

      {loading && <Loading label="Loading summary…" />}
      {!loading && error && <ErrorBanner error={error} title="Summary" />}

      {!loading && !error && data && (
        <div className="summary">
          <div className="summary__head">
            <span className="summary__name">{data.username}</span>
            <span className="summary__id">{data.user_id}</span>
          </div>
          <dl className="summary__grid">
            <div>
              <dt>Transactions</dt>
              <dd>{data.txn_count}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>{formatMoney(data.total_amount_cents)}</dd>
            </div>
            <div>
              <dt>Last activity</dt>
              <dd>{formatDate(data.last_txn_at)}</dd>
            </div>
          </dl>
        </div>
      )}

      {!loading && !error && !data && (
        <EmptyState message="Look up a user to see their summary." />
      )}
    </Card>
  );
}
