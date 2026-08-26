import { useCallback, useEffect, useState } from 'react';

// Phase 9: the real-backend replacement for each module's mock
// getSnapshot()/subscribe(cb, intervalMs) pair. Since a real fetch is
// async (unlike the mock's synchronous getSnapshot()), state starts as
// `null` and the first fetch resolves it -- every module's existing
// `if (!data?.field) return null` guard already handles that render.
export function useLiveResource(fetcher, intervalMs = 5000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(() => {
    fetcher()
      .then((next) => {
        setData(next);
        setError(null);
      })
      .catch((err) => {
        console.error('useLiveResource fetch failed:', err);
        setError(err);
      });
  }, [fetcher]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return [data, refresh, error];
}
