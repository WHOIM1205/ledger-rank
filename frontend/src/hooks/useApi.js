// The single place that owns loading/error/data mechanics for an async API
// call. Every feature component uses this so the three panels handle states
// identically and there is no duplicated try/catch.

import { useCallback, useState } from "react";
import { ApiError } from "../api/client.js";

// fn: an async function returning { data, status }.
// Returns { data, status, error, loading, run, reset }.
export function useApi(fn) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // run(...args) calls fn, updating state. Returns the result on success or
  // null on failure (the error is stored in `error`).
  const run = useCallback(
    async (...args) => {
      setLoading(true);
      setError(null);
      try {
        const result = await fn(...args);
        setData(result.data);
        setStatus(result.status);
        return result;
      } catch (err) {
        const apiErr =
          err instanceof ApiError
            ? err
            : new ApiError({ message: String(err) });
        setError(apiErr);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [fn]
  );

  const reset = useCallback(() => {
    setData(null);
    setStatus(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, status, error, loading, run, reset };
}
