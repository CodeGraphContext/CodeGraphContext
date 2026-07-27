// api/pypi.ts — proxy to pypistats.org for download counters

function pypiApiPath(reqUrl: string | undefined): string {
  if (!reqUrl) return "/packages/codegraphcontext/recent";

  try {
    const pathname = reqUrl.startsWith("http")
      ? new URL(reqUrl).pathname
      : reqUrl.split("?")[0];
    const stripped = pathname.replace(/^\/api\/pypi/, "") || "/packages/codegraphcontext/recent";
    return stripped.startsWith("/") ? stripped : `/${stripped}`;
  } catch {
    return "/packages/codegraphcontext/recent";
  }
}

export default async function handler(req: any, res: any) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=3600");

  const apiPath = pypiApiPath(req.url);
  const upstream = `https://pypistats.org/api${apiPath}`;

  try {
    const response = await fetch(upstream, {
      headers: { Accept: "application/json" },
    });

    const text = await response.text();
    if (!response.ok) {
      console.warn(`[pypi proxy] upstream ${response.status} for ${upstream}`);
      return res.status(200).json({
        type: "fallback",
        package: "codegraphcontext",
        data: { last_day: 1200, last_week: 8400, last_month: 36000 },
        error: `PyPI stats unavailable (${response.status})`,
      });
    }

    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      return res.status(200).json({
        type: "fallback",
        package: "codegraphcontext",
        data: { last_day: 1200, last_week: 8400, last_month: 36000 },
        error: "PyPI stats returned non-JSON response",
      });
    }

    return res.status(200).json(data);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[pypi proxy] fetch failed:", message);
    return res.status(200).json({
      type: "fallback",
      package: "codegraphcontext",
      data: { last_day: 1200, last_week: 8400, last_month: 36000 },
      error: "Failed to fetch PyPI stats",
    });
  }
}
