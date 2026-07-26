// Proxies GitLab archive downloads server-side so Sec-Fetch-* headers never reach GitLab.

import https from "https";

function parseGitlabZipPath(urlPath: string): { project: string; branch: string } | null {
  const segments = urlPath.split("/").filter(Boolean);
  // /api/gitlab-zip/:encodedProject/:branch
  if (segments.length < 4 || segments[0] !== "api" || segments[1] !== "gitlab-zip") {
    return null;
  }
  const encodedProject = segments[2];
  const branch = segments[3];
  if (!encodedProject || !branch) return null;

  let project = encodedProject;
  try {
    project = decodeURIComponent(encodedProject);
  } catch {
    project = encodedProject;
  }
  return { project, branch };
}

function fetchGitlabArchive(project: string, branch: string, token?: string): Promise<{
  statusCode: number;
  headers: Record<string, string | string[] | undefined>;
  body: Buffer;
}> {
  const gitlabPath = `/api/v4/projects/${encodeURIComponent(project)}/repository/archive.zip?sha=${encodeURIComponent(branch)}`;
  const headers: Record<string, string> = {
    "User-Agent": "CodeGraphContext-Website/1.0",
    Accept: "application/zip, application/octet-stream, */*",
  };
  if (token) {
    headers["PRIVATE-TOKEN"] = token;
  }

  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        hostname: "gitlab.com",
        path: gitlabPath,
        method: "GET",
        headers,
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          resolve({
            statusCode: res.statusCode || 500,
            headers: res.headers,
            body: Buffer.concat(chunks),
          });
        });
      }
    );
    req.on("error", reject);
    req.end();
  });
}

export default async function handler(req: any, res: any) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const rawUrl = req.url || "";
  const urlPath = rawUrl.split("?")[0];
  let parsed = parseGitlabZipPath(urlPath);

  if (!parsed && req.query?.project && req.query?.branch) {
    let project = String(req.query.project);
    try {
      project = decodeURIComponent(project);
    } catch {
      // keep raw value
    }
    parsed = { project, branch: String(req.query.branch) };
  }

  if (!parsed) {
    return res.status(400).json({ error: "Expected /api/gitlab-zip/:project/:branch" });
  }

  const token =
    (typeof req.headers?.["x-gitlab-token"] === "string" && req.headers["x-gitlab-token"]) ||
    (typeof req.headers?.["private-token"] === "string" && req.headers["private-token"]) ||
    undefined;

  try {
    const upstream = await fetchGitlabArchive(parsed.project, parsed.branch, token || undefined);
    res.status(upstream.statusCode);

    const contentType = upstream.headers["content-type"];
    const contentLength = upstream.headers["content-length"];
    const disposition = upstream.headers["content-disposition"];
    if (contentType) res.setHeader("Content-Type", contentType);
    if (contentLength) res.setHeader("Content-Length", contentLength);
    if (disposition) res.setHeader("Content-Disposition", disposition);
    res.setHeader("Cache-Control", "public, max-age=300");

    if (req.method === "HEAD") {
      return res.end();
    }

    return res.end(upstream.body);
  } catch (err: any) {
    console.error("[gitlab-zip] Proxy error:", err);
    return res.status(502).json({ error: "Failed to fetch GitLab archive", details: err.message });
  }
}
