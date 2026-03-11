import JSZip from 'jszip';
import type { FileData } from './astWorker';

export interface RepoConfig {
  url: string;
  token?: string;
}

export async function fetchRemoteRepo(config: RepoConfig, progressCallback: (msg: string) => void): Promise<FileData[]> {
  const { url, token } = config;
  
  let downloadUrl = '';
  let provider: 'github' | 'gitlab' | 'unknown' = 'unknown';
  let owner = '';
  let repo = '';

  try {
    const urlObj = new URL(url);
    if (urlObj.hostname.includes('github.com')) {
      provider = 'github';
      const parts = urlObj.pathname.split('/').filter(Boolean);
      owner = parts[0];
      repo = parts[1];
      
      let downloadPath = `zipball`;
      if (parts[2] === 'tree' && parts[3]) {
        downloadPath += `/${parts[3]}`;
      }
      downloadUrl = `https://api.github.com/repos/${owner}/${repo}/${downloadPath}`;
    } else if (urlObj.hostname.includes('gitlab.com')) {
      provider = 'gitlab';
      const parts = urlObj.pathname.split('/').filter(Boolean);
      repo = parts.pop()!;
      owner = parts.join('/');
      const projectPath = encodeURIComponent(`${owner}/${repo}`);
      downloadUrl = `https://gitlab.com/api/v4/projects/${projectPath}/repository/archive.zip`;
    } else {
      throw new Error('Unsupported repository provider. Only GitHub and GitLab are supported.');
    }
  } catch (err: any) {
    if (err instanceof Error) throw err;
    throw new Error('Invalid repository URL.');
  }

  progressCallback(`Fetching ${provider} repository...`);

  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  let finalDownloadUrl = downloadUrl;

  // In production (Vercel), we must use our serverless proxy to bypass CORS redirects
  if (!isDev) {
    const proxyUrl = new URL('/api/proxy', window.location.origin);
    proxyUrl.searchParams.set('url', downloadUrl);
    proxyUrl.searchParams.set('provider', provider);
    if (token) proxyUrl.searchParams.set('token', token);
    finalDownloadUrl = proxyUrl.toString();
  } else {
    // Use Vite proxies in development
    if (provider === 'github') {
      finalDownloadUrl = downloadUrl.replace('https://api.github.com', '/proxy/github-api');
    } else if (provider === 'gitlab') {
      finalDownloadUrl = downloadUrl.replace('https://gitlab.com', '/proxy/gitlab');
    }
  }

  const headers: HeadersInit = {};
  if (token) {
    if (provider === 'github') {
      headers['Authorization'] = `token ${token}`;
    } else if (provider === 'gitlab') {
      headers['PRIVATE-TOKEN'] = token;
    }
  }

  // The proxy is configured with manual Location rewriting, so it will handle
  // the GitHub -> CodeLoad redirect and return the final zip binary.
  const response = await fetch(finalDownloadUrl, { headers });
  
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Repository or branch not found. If it is private, please provide a token.');
    }
    throw new Error(`Failed to fetch repository: ${response.statusText}`);
  }

  const blob = await response.blob();
  progressCallback('Extracting archive...');
  
  const zip = await JSZip.loadAsync(blob);
  const fileEntries: FileData[] = [];
  // Common text extensions (broad list for explorer visibility)
  const textExts = new Set(['.js', '.jsx', '.ts', '.tsx', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.sh', '.bash', '.sql', '.html', '.css', '.scss', '.json', '.xml', '.yaml', '.yml', '.md', '.txt', '.env', '.toml', '.proto', '.graphql', '.svelte', '.vue', '.astro', '.properties', '.gradle', '.lock']);

  const zipPaths = Object.keys(zip.files);
  if (zipPaths.length === 0) return [];

  const firstPath = zipPaths[0];
  const rootFolder = firstPath.split('/')[0] + '/';
  const hasRootFolder = zipPaths.every(p => p.startsWith(rootFolder));

  for (const [path, file] of Object.entries(zip.files)) {
    if (file.dir) continue;
    
    let normalizedPath = hasRootFolder ? path.substring(rootFolder.length) : path;
    const name = normalizedPath.split('/').pop() || '';
    const ext = name.substring(name.lastIndexOf('.')).toLowerCase();
    
    // Ignore common binary/dependency folders
    const segments = normalizedPath.split('/');
    const isIgnored = segments.some(s => 
      ['node_modules', '.git', 'dist', 'target', 'build', 'out', '.next', '.cache', 'vendor'].includes(s)
    );
    
    if (isIgnored) continue;

    // Check if it's likely a text file
    const isText = textExts.has(ext) || !name.includes('.'); // Include files with no extension too
    if (!isText) continue;

    const content = await file.async('string');
    fileEntries.push({ path: normalizedPath, content });
  }

  return fileEntries;
}
