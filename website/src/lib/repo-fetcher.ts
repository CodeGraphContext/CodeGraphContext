import JSZip from "jszip";
import {
  RepoRef,
  getAuthHeaders,
  getAuthTokenKey,
  getAuthenticatedZipUrl,
  getBranchesToTry,
  getCdnFileUrl,
  getPublicZipUrl,
  getRawFileUrl,
  getZipProxyUrl,
  estimateZipSize,
  listRepositoryFiles,
  resolveRepoMetadata,
} from "./repo-provider";

const SOURCE_FILE_PATTERN = /\.(js|ts|jsx|tsx|py|c|h|cpp|hpp|cc|cs|go|rs|rb|php|swift|kt|kts|dart)$/;

export interface FetchedRepoFiles {
  files: { path: string; content: string }[];
  fileContents: Record<string, string>;
  latestCommitSha: string;
  detectedBranch: string;
}

export interface RepoFetchCallbacks {
  onProgressText: (text: string) => void;
  onProgressValue: (value: number) => void;
  isPathIgnored: (path: string) => boolean;
  fetchWithProgress: (url: string, onProgress: (loaded: number, total: number) => void) => Promise<Response>;
  fetchWithFallbackProxies: (
    url: string,
    onProgress?: (loaded: number, total: number) => void
  ) => Promise<Response>;
}

const isZipResponse = (res: Response) => {
  const contentType = res.headers.get("content-type") || "";
  return !contentType.includes("text/html") && !contentType.includes("application/json");
};

export async function fetchRepositoryFiles(
  ref: RepoRef,
  callbacks: RepoFetchCallbacks
): Promise<FetchedRepoFiles> {
  const { onProgressText, onProgressValue, isPathIgnored, fetchWithProgress, fetchWithFallbackProxies } =
    callbacks;

  let files: { path: string; content: string }[] = [];
  let fileContents: Record<string, string> = {};

  const { detectedBranch, latestCommitSha: initialCommitSha } = await resolveRepoMetadata(ref);
  let latestCommitSha = initialCommitSha;
  const branchesToTry = getBranchesToTry(detectedBranch);
  const { estimatedZipSize, isEstimateReliable } = await estimateZipSize(ref, branchesToTry);

  const updateDownloadProgress = (loaded: number, total: number) => {
    const mbLoaded = (loaded / 1024 / 1024).toFixed(2);
    const finalTotal = total > 0 ? total : estimatedZipSize;

    let pct = 0;
    if (loaded < finalTotal) {
      pct = Math.round((loaded / finalTotal) * 90);
    } else {
      const overflow = loaded - finalTotal;
      const extraPct = 9 * (1 - Math.exp(-overflow / (1024 * 1024 * 5)));
      pct = Math.round(90 + extraPct);
    }

    if (total > 0) {
      onProgressText(
        `Downloading repository archive: ${pct}% (${mbLoaded} MB of ${(total / 1024 / 1024).toFixed(2)} MB)`
      );
    } else if (isEstimateReliable) {
      onProgressText(
        `Downloading repository archive: ${pct}% (${mbLoaded} MB of ~${(estimatedZipSize / 1024 / 1024).toFixed(2)} MB)`
      );
    } else {
      onProgressText(`Downloading repository archive: ${pct}% (${mbLoaded} MB)`);
    }
    onProgressValue(10 + Math.floor(pct * 0.15));
  };

  try {
    onProgressText("Downloading repository archive...");
    onProgressValue(10);

    let response: Response | null = null;
    let zipSuccessBranch = detectedBranch;
    const authHeaders = getAuthHeaders(ref);

    if (localStorage.getItem(getAuthTokenKey(ref))) {
      for (const branch of branchesToTry) {
        try {
          const zipUrl = getAuthenticatedZipUrl(ref, branch);
          if (!zipUrl) continue;
          const tempRes = await fetch(zipUrl, { headers: authHeaders });
          if (tempRes.ok) {
            response = tempRes;
            zipSuccessBranch = branch;
            break;
          }
        } catch (errAuth) {
          console.warn(`[Explore] Authenticated zip failed for branch ${branch}:`, errAuth);
        }
      }
    }

    if (!response || !response.ok) {
      for (const branch of branchesToTry) {
        try {
          const zipUrl = getZipProxyUrl(ref, branch);
          const tempRes = await fetchWithProgress(zipUrl, updateDownloadProgress);
          if (tempRes?.ok && isZipResponse(tempRes)) {
            response = tempRes;
            zipSuccessBranch = branch;
            break;
          }
        } catch (err1) {
          console.warn(`[Explore] Same-origin zip proxy failed for branch ${branch}:`, err1);
        }
      }
    }

    if (!response || !response.ok) {
      for (const branch of branchesToTry) {
        try {
          const zipUrl = getPublicZipUrl(ref, branch);
          const tempRes = await fetchWithFallbackProxies(zipUrl, updateDownloadProgress);
          if (tempRes?.ok && isZipResponse(tempRes)) {
            response = tempRes;
            zipSuccessBranch = branch;
            break;
          }
        } catch (err3) {
          console.warn(`[Explore] Public zip fallback failed for branch ${branch}:`, err3);
        }
      }
    }

    if (!response || !response.ok) {
      throw new Error("All ZIP download tiers failed.");
    }

    onProgressText("Unzipping archive in-memory...");
    onProgressValue(30);
    const buffer = await response.arrayBuffer();
    const jszip = await JSZip.loadAsync(buffer);

    const promises: Promise<void>[] = [];
    jszip.forEach((path, entry) => {
      if (!entry.dir && SOURCE_FILE_PATTERN.test(path) && !isPathIgnored(path)) {
        promises.push(
          entry.async("text").then((content) => {
          .catch(err => console.error(err))