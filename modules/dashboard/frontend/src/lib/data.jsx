import { createContext, useContext, useEffect, useState } from "react";

/**
 * Loads the static JSON exported by `python -m modules.dashboard.build`
 * (served from public/data/) once on mount. Pure local fetch — no external network.
 */
const DataCtx = createContext(null);

const FILES = ["incidents", "events", "metrics", "reports", "notifications", "replay"];

export function DataProvider({ children }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const base = import.meta.env.BASE_URL || "/";
        const results = await Promise.all(
          FILES.map((f) =>
            fetch(`${base}data/${f}.json`).then((r) => {
              if (!r.ok) throw new Error(`Failed to load ${f}.json (${r.status})`);
              return r.json();
            })
          )
        );
        if (!alive) return;
        const obj = {};
        FILES.forEach((f, i) => (obj[f] = results[i]));
        setData(obj);
      } catch (e) {
        if (alive) setError(e);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return <DataCtx.Provider value={{ data, loading, error }}>{children}</DataCtx.Provider>;
}

export function useData() {
  const ctx = useContext(DataCtx);
  if (!ctx) throw new Error("useData must be used within <DataProvider>");
  return ctx;
}
