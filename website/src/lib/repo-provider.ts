export type RepoProvider = "github" | "gitlab";

export interface RepoRef {
  provider: RepoProvider;
  /** Namespace / owner segment (may contain slashes for nested GitLab groups). */
  owner: string;
  /** Project / repository name. */
  repo: string;
  /** Full project path, e.g. `gitlab-org/gitlab` or `facebook/react`. */
  fullPath: string;
  host: string;
}

const GITHUB_HOST = "github.com";
const GITLAB_HOST = "gitlab.com";

const DEFAULT_BRANCHES = ["main", "master", "unstable", "trunk", "develop", "dev"];

/** Strip trailing .git, /-/* UI paths, and query/hash from a repo path segment. */
export function cleanRepoPathSegment(path: string): string {
  return path
    .replace(/\.git$/, "")
    .replace(/\/-$/, "")
    .replace(/\/-\/.*$/, "")
    .replace(/[?#].*$/, "")
    .replace(/\/$/, "");
}

/** Parse a user-supplied URL or `owner/repo` shorthand into a RepoRef. */
export function parseRepoInput(input: string): RepoRef | null {
  const trimmed = input.trim();
  if (!trimmed) return null;

  const gitlabMatch = trimmed.match(/gitlab\.com\/([^?#]+)/i);
  if (gitlabMatch) {
    const path = cleanRepoPathSegment(gitlabMatch[1]);
    const parts = path.split("/").filter(Boolean);
    if (parts.length < 2) return null;
    const repo = parts[parts.length - 1];
    const owner = parts.slice(0, -1).join("/");
    return {
      provider: "gitlab",
      owner,
      repo,
      fullPath: `${owner}/${repo}`,
      host: GITLAB_HOST,
    };
  }

  const githubMatch = trimmed.match(/github\.com\/([^/]+)\/([^/?#]+)/i);
  if (githubMatch) {
    const owner = githubMatch[1];
    const repo = githubMatch[2].replace(/\.git$/, "");
    return {
      provider: "github",
      owner,
      repo,
      fullPath: `${owner}/${repo}`,
      host: GITHUB_HOST,
    };
  }

  const shorthand = trimmed.match(/^([^/]+\/[^/]+(?:\/[^/]+)*)\/?$/);
  if (shorthand) {
    const path = cleanRepoPathSegment(shorthand[1]);
    const parts = path.split("/").filter(Boolean);
    if (parts.length < 2) return null;
    const repo = parts[parts.length - 1];
    const owner = parts.slice(0, -1).join("/");
    return {
      provider: "github",
      owner,
      repo,
      fullPath: `${owner}/${repo}`,
      host: GITHUB_HOST,
    };
  }

  return null;
}

/** Build a RepoRef from route parameters. */
export function repoRefFromRoute(
  provider: RepoProvider | undefined,
  owner: string | undefined,
  repo: string | undefined,
  gitlabSplat?: string
): RepoRef | null {
  if (provider === "gitlab") {
    const fullPath = cleanRepoPathSegment(gitlabSplat || "");
    if (!fullPath) return null;
    const parts = fullPath.split("/").filter(Boolean);
    if (parts.length < 2) return null;
    const repoName = parts[parts.length - 1];
    const ownerPath = parts.slice(0, -1).join("/");
    return {
      provider: "gitlab",
      owner: ownerPath,
      repo: repoName,
      fullPath,
      host: GITLAB_HOST,
    };
  }

  if (!owner || !repo) return null;
  return {
    provider: provider === "github" ? "github" : "github",
    owner,
    repo,
    fullPath: `${owner}/${repo}`,
    host: GITHUB_HOST,
  };
}

/** Guess provider from partial user input (URL or shorthand). Defaults to GitHub. */
export function detectProviderFromInput(input: string): RepoProvider {
  const trimmed = input.trim().toLowerCase();
  if (trimmed.includes("gitlab.com") || trimmed.includes("gitlab:")) {
    return "gitlab";
  }
  return "github";
}

export function getExploreRoute(ref: RepoRef): string {
  if (ref.provider === "gitlab") {
    return `/gitlab/${ref.fullPath}`;
  }
  return `/${ref.owner}/${ref.repo}`;
}

export function getCacheKey(ref: RepoRef): string {
  return `${ref.provider}:${ref.fullPath.toLowerCase()}`;
}

export function getLegacyCacheKey(ref: RepoRef): string {
  return `${ref.owner.toLowerCase()}/${ref.repo.toLowerCase()}`;
}

export function getAuthTokenKey(ref: RepoRef): string {
  return ref.provider === "gitlab" ? "gitlab_pat" : "github_pat";
}

export function getAuthHeaders(ref: RepoRef): Record<string, string> {
  const token = localStorage.getItem(getAuthTokenKey(ref));
  if (!token) return {};
  if (ref.provider === "gitlab") {
    return { "PRIVATE-TOKEN": token };
  }
  return { Authorization: `token ${token}` };
}

export function getBranchesToTry(detectedBranch: string): string[] {
  return Array.from(new Set([detectedBranch, ...DEFAULT_BRANCHES]));
}

/** Resolve default branch and latest commit SHA for a repository. */
export async function resolveRepoMetadata(
  ref: RepoRef
): Promise<{ detectedBranch: string; latestCommitSha: string }> {
  let detectedBranch = "main";
  let latestCommitSha = "";

  const headers = getAuthHeaders(ref);

  try {
    if (ref.provider === "github") {
      const apiRes = await fetch(
        `https://api.github.com/repos/${ref.owner}/${ref.repo}`,
        { headers }
      );
      if (apiRes.ok) {
        const apiData = await apiRes.json();
        if (apiData?.default_branch) {
          detectedBranch = apiData.default_branch;
        }
      }

      const commitsRes = await fetch(
        `https://api.github.com/repos/${ref.owner}/${ref.repo}/commits/${detectedBranch}`,
        { headers }
      );
      if (commitsRes.ok) {
        const commitsData = await commitsRes.json();
        if (commitsData?.sha) {
          latestCommitSha = commitsData.sha;
        }
      }
    } else {
      const projectPath = encodeURIComponent(ref.fullPath);
      const apiRes = await fetch(
        `https://gitlab.com/api/v4/projects/${projectPath}`,
        { headers }
      );
      if (apiRes.ok) {
        const apiData = await apiRes.json();
        if (apiData?.default_branch) {
          detectedBranch = apiData.default_branch;
        }
        if (apiData?.last_commit_id) {
          latestCommitSha = apiData.last_commit_id;
        }
      }
    }
  } catch (err) {
    console.warn(`[Explore] Failed to resolve branch metadata for ${ref.fullPath}:`, err);
  }

  return { detectedBranch, latestCommitSha };
}

export function getZipProxyUrl(ref: RepoRef, branch: string): string {
  if (ref.provider === "gitlab") {
    return `/api/gitlab-zip/${encodeURIComponent(ref.fullPath)}/${branch}`;
  }
  return `/api/github-zip/${ref.owner}/${ref.repo}/${branch}`;
}

export function getPublicZipUrl(ref: RepoRef, branch: string): string {
  if (ref.provider === "gitlab") {
    return `https://gitlab.com/${ref.fullPath}/-/archive/${branch}/${ref.repo}-${branch}.zip`;
  }
  return `https://github.com/${ref.owner}/${ref.repo}/archive/refs/heads/${branch}.zip`;
}

export function getAuthenticatedZipUrl(ref: RepoRef, branch: string): string | null {
  const token = localStorage.getItem(getAuthTokenKey(ref));
  if (!token) return null;

  if (ref.provider === "gitlab") {
    const projectPath = encodeURIComponent(ref.fullPath);
    return `https://gitlab.com/api/v4/projects/${projectPath}/repository/archive.zip?sha=${branch}`;
  }
  return `https://api.github.com/repos/${ref.owner}/${ref.repo}/zipball/${branch}`;
}

export function getJsdelivrMetaUrl(ref: RepoRef, branch: string): string | null {
  if (ref.provider !== "github") return null;
  return `https://data.jsdelivr.net/v1/packages/gh/${ref.owner}/${ref.repo}@${branch}`;
}

export function getRawFileUrl(ref: RepoRef, branch: string, filePath: string): string {
  if (ref.provider === "gitlab") {
    return `https://gitlab.com/${ref.fullPath}/-/raw/${branch}/${filePath}`;
  }
  return `https://raw.githubusercontent.com/${ref.owner}/${ref.repo}/${branch}/${filePath}`;
}

export function getCdnFileUrl(ref: RepoRef, branch: string, filePath: string): string | null {
  if (ref.provider === "github") {
    return `https://cdn.jsdelivr.net/gh/${ref.owner}/${ref.repo}@${branch}/${filePath}`;
  }
  return null;
}

/** List all file paths in a repository (fallback when ZIP download fails). */
export async function listRepositoryFiles(
  ref: RepoRef,
  branchesToTry: string[]
): Promise<{ files: string[]; branch: string; commitSha: string }> {
  const headers = getAuthHeaders(ref);
  let filesList: string[] = [];
  let successBranch = branchesToTry[0] || "main";
  let commitSha = "";

  if (ref.provider === "github") {
    for (const branch of branchesToTry) {
      const jsdelivrMetaUrl = getJsdelivrMetaUrl(ref, branch);
      if (jsdelivrMetaUrl) {
        try {
          const metaRes = await fetch(jsdelivrMetaUrl);
          if (metaRes.ok) {
            const metaData = await metaRes.json();
            if (metaData?.files && Array.isArray(metaData.files)) {
              filesList = flattenJsdelivrTree(metaData.files);
              successBranch = branch;
              if (metaData.version) commitSha = metaData.version;
              break;
            }
          }
        } catch (e) {
          console.warn(`[Explore] jsDelivr listing failed for @${branch}:`, e);
        }
      }
    }

    if (filesList.length === 0) {
      for (const branch of branchesToTry) {
        try {
          const treeResponse = await fetch(
            `https://api.github.com/repos/${ref.owner}/${ref.repo}/git/trees/${branch}?recursive=true`,
            { headers }
          );
          if (treeResponse.ok) {
            const treeData = await treeResponse.json();
            if (treeData?.tree && Array.isArray(treeData.tree)) {
              filesList = treeData.tree
                .filter((item: { type: string }) => item.type === "blob")
                .map((item: { path: string }) => item.path);
              successBranch = branch;
              break;
            }
          }
        } catch (e) {
          console.warn(`[Explore] GitHub tree listing failed for @${branch}:`, e);
        }
      }
    }
  } else {
    const projectPath = encodeURIComponent(ref.fullPath);
    for (const branch of branchesToTry) {
      try {
        let page = 1;
        const pageFiles: string[] = [];
        while (page <= 50) {
          const treeResponse = await fetch(
            `https://gitlab.com/api/v4/projects/${projectPath}/repository/tree?recursive=true&per_page=100&page=${page}&ref=${encodeURIComponent(branch)}`,
            { headers }
          );
          if (!treeResponse.ok) break;
          const treeData = await treeResponse.json();
          if (!Array.isArray(treeData) || treeData.length === 0) break;
          pageFiles.push(
            ...treeData
              .filter((item: { type: string }) => item.type === "blob")
              .map((item: { path: string }) => item.path)
          );
          const nextPage = treeResponse.headers.get("x-next-page");
          if (!nextPage || nextPage === "") break;
          page = parseInt(nextPage, 10) || page + 1;
        }
        if (pageFiles.length > 0) {
          filesList = pageFiles;
          successBranch = branch;
          break;
        }
      } catch (e) {
        console.warn(`[Explore] GitLab tree listing failed for @${branch}:`, e);
      }
    }
  }

  return { files: filesList, branch: successBranch, commitSha };
}

interface JsdelivrFile {
  name: string;
  type: "file" | "directory";
  size?: number;
  files?: JsdelivrFile[];
}

function flattenJsdelivrTree(items: JsdelivrFile[], currentPath = ""): string[] {
  let filePaths: string[] = [];
  for (const item of items) {
    const itemPath = currentPath ? `${currentPath}/${item.name}` : item.name;
    if (item.type === "file") {
      filePaths.push(itemPath);
    } else if (item.type === "directory" && item.files) {
      filePaths.push(...flattenJsdelivrTree(item.files, itemPath));
    }
  }
  return filePaths;
}

export function getJsdelivrTotalSize(items: JsdelivrFile[]): number {
  let total = 0;
  for (const item of items) {
    if (item.type === "file" && item.size) {
      total += item.size;
    } else if (item.type === "directory" && item.files) {
      total += getJsdelivrTotalSize(item.files);
    }
  }
  return total;
}

export async function estimateZipSize(
  ref: RepoRef,
  branchesToTry: string[]
): Promise<{ estimatedZipSize: number; isEstimateReliable: boolean }> {
  let estimatedZipSize = 4 * 1024 * 1024;
  let isEstimateReliable = false;

  if (ref.provider !== "github") {
    return { estimatedZipSize, isEstimateReliable };
  }

  for (const branch of branchesToTry) {
    const jsdelivrMetaUrl = getJsdelivrMetaUrl(ref, branch);
    if (!jsdelivrMetaUrl) continue;
    try {
      const metaRes = await fetch(jsdelivrMetaUrl);
      if (metaRes.ok) {
        const metaData = await metaRes.json();
        if (metaData?.files && Array.isArray(metaData.files)) {
          const uncompressedSize = getJsdelivrTotalSize(metaData.files);
          if (uncompressedSize > 0) {
            estimatedZipSize = Math.max(500 * 1024, uncompressedSize * 0.22);
            isEstimateReliable = true;
          }
          break;
        }
      }
    } catch (err) {
      console.warn(`[Explore] Failed jsDelivr metadata fetch for branch ${branch}:`, err);
    }
  }

  return { estimatedZipSize, isEstimateReliable };
}
