import type { VercelRequest, VercelResponse } from '@vercel/node';

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const { url, token, provider } = req.query;

  if (!url || typeof url !== 'string') {
    return res.status(400).json({ error: 'Missing URL' });
  }

  try {
    const headers: HeadersInit = {};
    if (token && typeof token === 'string') {
      if (provider === 'github') {
        headers['Authorization'] = `token ${token}`;
      } else if (provider === 'gitlab') {
        headers['PRIVATE-TOKEN'] = token;
      }
    }

    const response = await fetch(url, { headers });

    if (!response.ok) {
      return res.status(response.status).json({ error: `Failed to fetch: ${response.statusText}` });
    }

    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // Set CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', 'attachment; filename=repo.zip');

    return res.send(buffer);
  } catch (error: any) {
    console.error('Proxy error:', error);
    return res.status(500).json({ error: error.message });
  }
}
