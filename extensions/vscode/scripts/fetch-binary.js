#!/usr/bin/env node
/* eslint-disable no-console */

// Downloads the platform-matched cgc binary from the latest GitHub release
// into extensions/vscode/bin/. Wired into vscode:prepublish.
//
// Env: CGC_BINARY_REPO, CGC_BINARY_TAG, CGC_BINARY_PLATFORM, CGC_BINARY_ARCH, CGC_BINARY_SKIP.

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
  console.warn(`[fetch-binary] No prebuilt binary for ${PLATFORM}/${ARCH}; falling back to PATH at runtime.`);
  process.exit(0);
}

const BIN_DIR = path.join(__dirname, "..", "bin");
const OUT_PATH = path.join(BIN_DIR, ARTIFACT);

fs.mkdirSync(BIN_DIR, { recursive: true });

// Follows redirects — release asset URLs 302 to s3.
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
    throw new Error(`Release ${release.tag_name || TAG} has no asset named "${ARTIFACT}".`);
  }

  console.log(`[fetch-binary] Downloading ${ARTIFACT} from ${release.tag_name} (${(asset.size / 1e6).toFixed(1)} MB)`);
  await downloadTo(asset.browser_download_url, OUT_PATH);

  if (PLATFORM !== "win32") {
    fs.chmodSync(OUT_PATH, 0o755);
  }
  console.log(`[fetch-binary] Wrote ${OUT_PATH}`);
}

// Fail soft — runtime resolver falls back to PATH if the binary's missing.
main().catch((err) => {
  console.warn(`[fetch-binary] Skipped: ${err.message}`);
  process.exit(0);
});
