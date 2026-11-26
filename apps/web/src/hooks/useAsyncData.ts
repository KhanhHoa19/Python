import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncData<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** Load data once and on demand; ignores results from superseded requests. */
export function useAsyncData<T>(loader: () => Promise<T>, deps: React.DependencyList, enabled = true): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const latest = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const id = ++latest.current;
    setLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (id === latest.current) setData(result);
      })
      .catch((err: unknown) => {
        if (id === latest.current) setError(err instanceof Error ? err.message : 'Đã xảy ra lỗi.');
      })
      .finally(() => {
        if (id === latest.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, reload };
}
