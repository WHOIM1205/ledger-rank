// Leaderboard panel. Fetches GET /ranking and renders the multi-factor score
// for each user, with a small inline bar so fairness is visible. Auto-refreshes
// when refreshKey changes (after a transaction).

import { useEffect } from "react";
import { useApi } from "../../hooks/useApi.js";
import { getRanking } from "../../api/endpoints.js";
import { formatMoney } from "../../lib/format.js";
import Card from "../ui/Card.jsx";
import ErrorBanner from "../ui/ErrorBanner.jsx";
import Loading from "../ui/Loading.jsx";
import EmptyState from "../ui/EmptyState.jsx";

export default function RankingLeaderboard({ refreshKey }) {
  const { data, error, loading, run } = useApi(getRanking);

  useEffect(() => {
    run({ limit: 50, offset: 0 });
  }, [refreshKey, run]);

  const rankings = data?.rankings ?? [];

  return (
    <Card
      title="Ranking Leaderboard"
      subtitle="Score = 0.5·amount + 0.3·count + 0.2·recency (amount & count log-scaled)."
    >
      {loading && <Loading label="Loading ranking…" />}
      {!loading && error && <ErrorBanner error={error} title="Ranking" />}

      {!loading && !error && rankings.length === 0 && (
        <EmptyState message="No ranked users yet. Create a transaction to begin." />
      )}

      {!loading && !error && rankings.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>User</th>
              <th>Score</th>
              <th className="num">Txns</th>
              <th className="num">Total</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r) => (
              <tr key={r.user_id}>
                <td className="rank">{r.rank}</td>
                <td>
                  <span className="table__name">{r.username}</span>
                  <span className="table__id">{r.user_id}</span>
                </td>
                <td>
                  <div className="scorebar">
                    <div
                      className="scorebar__fill"
                      style={{ width: `${Math.max(2, r.score)}%` }}
                    />
                    <span className="scorebar__value">
                      {r.score.toFixed(2)}
                    </span>
                  </div>
                </td>
                <td className="num">{r.txn_count}</td>
                <td className="num">{formatMoney(r.total_amount_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
