import { useEffect, useState } from "react";

const LAST_MONTH_KEY = "cgc_last_month_downloads";
type PypiStats = {
  data: {
    last_day: number;
    last_month: number;
    last_week: number;
  };
  package: string;
  type: string;
};

export default function ShowDownloads() {
  const [stats, setStats] = useState<PypiStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
   async function fetchStats() {
  try {
    const res = await fetch("/api/pypi/packages/codegraphcontext/recent");

    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }

    const data = await res.json();

    //  Save last successful monthly downloads
    if (data?.data?.last_month) {
      localStorage.setItem(
        LAST_MONTH_KEY,
        data.data.last_month.toString()
      );
    }

    setStats(data);
  } catch (err: unknown) {
    //  Trying to use last saved value
    const savedLastMonth = localStorage.getItem(LAST_MONTH_KEY);

    if (savedLastMonth) {
      setStats({
        data: {
          last_day: 0,
          last_week: 0,
          last_month: Number(savedLastMonth),
        },
        package: "codegraphcontext",
        type: "fallback",
      });
    } else {
      setError((err as Error).message);
    }
  }
}

    fetchStats();
  }, []);

  if (error) return <p className="text-red-500">Error: {error}</p>;
  if (!stats) return <p>Loading stats...</p>;

  return (
    <div>
      {stats?.data ? (
        <>
          <p>Last month downloads: {stats.data.last_month.toLocaleString()}+</p>
        </>
      ) : (
        <p>No data available yet for this package</p>
      )}
    </div>
  );
}