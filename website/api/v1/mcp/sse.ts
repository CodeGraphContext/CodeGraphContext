// website/api/v1/mcp/sse.ts
export default async function handler(req: any, res: any) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: `Method ${req.method} not allowed` });
  }

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");

  const sessionId = Math.random().toString(36).substring(2, 15);
  const host = req.headers.host || "codegraphcontext.vercel.app";
  const protocol = req.headers["x-forwarded-proto"] || "https";
  const messagesUrl = `${protocol}://${host}/api/v1/mcp/messages?sessionId=${sessionId}`;

  res.write(`event: endpoint\ndata: ${messagesUrl}\n\n`);

  const keepAlive = setInterval(() => {
    res.write(": keepalive\n\n");
  }, 10000);

  req.on("close", () => {
    clearInterval(keepAlive);
    res.end();
  });
}
