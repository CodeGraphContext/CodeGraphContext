#!/usr/bin/env node
/* eslint-disable no-console */

// Pulls the platform-matched cgc binary from the latest GitHub release
// and drops it in extensions/vscode/bin/. Runs as part of vscode:prepublish
// so the VSIX we ship to the marketplace already contains the executable.
//
// Env knobs:
//   CGC_BINARY_REPO     owner/repo           (default CodeGraphContext/CodeGraphContext)
//   CGC_BINARY_TAG      e.g. v0.4.10         (default: latest)
//   CGC_BINARY_PLATFORM win32|darwin|linux   (override auto-detect, useful in CI)
//   CGC_BINARY_ARCH     x64|arm64            (override auto-detect)
//   CGC_BINARY_SKIP=1   bail out early       (for `npm install` without network)

const fs = require("fs");
const path = require("path");
const https = require("https");

const REPO = process.env.CGC_BINARY_REPO || "CodeGraphContext/CodeGraphContext";
const TAG = process.env.CGC_BINARY_TAG || "latest";
const PLATFORM = process.env.CGC_BINARY_PLATFORM || process.platform;
const ARCH = process.env.CGC_BINARY_ARCH || process.arch;

if (process.env.CGC_BINARY_SKIP === "1") {
  console.log("[fetch-binary] CGC_BINARY_SKIP=1, doing nothing.");
  process.exit(0);
}

function artifactFor(platform, arch) {
  if (platform === "win32") return "cgc-windows.exe";
  if (platform === "darwin" && arch === "arm64") return "cgc-macos-arm64";
  if (platform === "linux" && arch === "x64") return "cgc-linux-x86_64";
  return null;
}

const ARTIFACT = artifactFor(PLATFORM, ARCH);
if (!ARTIFACT) {
  console.warn(
    `[fetch-binary] No prebuilt binary for ${PLATFORM}/${ARCH}. ` +
      `The extension will fall back to 'cgc' on PATH at runtime.`
  );
  process.exit(0);
}

const BIN_DIR = path.join(__dirname, "..", "bin");
const OUT_PATH = path.join(BIN_DIR, ARTIFACT);

fs.mkdirSync(BIN_DIR, { recursive: true });

// Tiny GET wrapper that follows redirects. The GitHub release asset URL bounces
// through s3 with a 302, and node's https client won't chase that for us.
function get(url, headers) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        resolve(get(res.headers.location, headers));
        return;
      }
      resolve(res);
    });
    req.on("error", reject);
  });
}

async function readJson(url) {
  const res = await get(url, {
    "User-Agent": "cgc-vscode-fetch-binary",
    Accept: "application/vnd.github+json",
  });
  if (res.statusCode !== 200) {
    throw new Error(`GitHub API ${url} returned ${res.statusCode}`);
  }
  const chunks = [];
  for await (const c of res) chunks.push(c);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function downloadTo(url, dest) {
  const res = await get(url, {
    "User-Agent": "cgc-vscode-fetch-binary",
    Accept: "application/octet-stream",
  });
  if (res.statusCode !== 200) {
    throw new Error(`Download of ${url} failed with ${res.statusCode}`);
  }
  await new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    res.pipe(file);
    file.on("finish", () => file.close(() => resolve()));
    file.on("error", reject);
  });
}

async function main() {
  const apiUrl =
    TAG === "latest"
      ? `https://api.github.com/repos/${REPO}/releases/latest`
      : `https://api.github.com/repos/${REPO}/releases/tags/${TAG}`;

  console.log(`[fetch-binary] Looking up ${apiUrl}`);
  const release = await readJson(apiUrl);

  const asset = (release.assets || []).find((a) => a.name === ARTIFACT);
  if (!asset) {
    throw new Error(
      `Release ${release.tag_name || TAG} doesn't expose an asset named "${ARTIFACT}".`
    );
  }

  console.log(
    `[fetch-binary] Downloading ${ARTIFACT} from release ${release.tag_name} (${(asset.size / 1e6).toFixed(1)} MB)`
  );
  await downloadTo(asset.browser_download_url, OUT_PATH);

  if (PLATFORM !== "win32") {
    fs.chmodSync(OUT_PATH, 0o755);
  }
  console.log(`[fetch-binary] Wrote ${OUT_PATH}`);
}

main().catch((err) => {
  // Don't abort the whole `npm install` over a flaky network — the runtime
  // resolver falls back to PATH and tells the user how to recover.
  console.warn(`[fetch-binary] Skipped: ${err.message}`);
  process.exit(0);
});
