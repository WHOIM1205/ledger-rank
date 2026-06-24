// Root component. Owns the two pieces of cross-cutting state:
//   1. refreshKey       -> bumped after a transaction to refresh Summary+Ranking
//   2. health state      -> backend availability (polls GET /health)
// Everything else lives inside the feature panels.

import { useCallback, useEffect, useState } from "react";
import { getHealth } from "./api/endpoints.js";
import HealthIndicator from "./components/ui/HealthIndicator.jsx";
import TransactionForm from "./components/features/TransactionForm.jsx";
import UserSummary from "./components/features/UserSummary.jsx";
import RankingLeaderboard from "./components/features/RankingLeaderboard.jsx";

const HEALTH_POLL_MS = 15000;

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [health, setHealth] = useState("checking"); // checking | online | offline

  // Single callback passed to the form; bumping the key re-fetches the
  // dependent panels (Summary + Leaderboard).
  const handleTransactionApplied = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  // Poll backend health immediately on load, then on a light interval.
  useEffect(() => {
    let active = true;
    async function ping() {
      try {
        await getHealth();
        if (active) setHealth("online");
      } catch {
        if (active) setHealth("offline");
      }
    }
    ping();
    const id = setInterval(ping, HEALTH_POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="app">
      <header className="app__bar">
        <div className="app__brand">
          <span className="app__logo">▦</span>
          <div>
            <h1 className="app__title">LedgerRank</h1>
            <p className="app__tagline">
              Idempotent ledger · concurrency-safe aggregates · fair ranking
            </p>
          </div>
        </div>
        <HealthIndicator state={health} />
      </header>

      <main className="app__main">
        <div className="app__grid">
          <TransactionForm onTransactionApplied={handleTransactionApplied} />
          <UserSummary refreshKey={refreshKey} />
        </div>
        <RankingLeaderboard refreshKey={refreshKey} />
      </main>

      <footer className="app__footer">
        <span>LedgerRank demo</span>
        <a href={`${import.meta.env.VITE_API_BASE_URL || ""}/docs`} target="_blank" rel="noreferrer">
          API docs ↗
        </a>
      </footer>
    </div>
  );
}
