const ipRateLimits = new Map();
const repoCooldowns = new Map();
const activeRepoJobs = new Map();

const DEFAULT_RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000;
const DEFAULT_RATE_LIMIT_MAX = 10;
const DEFAULT_REPO_COOLDOWN_MS = 5 * 60 * 1000;
const DEFAULT_ACTIVE_JOB_TTL_MS = 45 * 60 * 1000;

function parsePositiveInt(rawValue, fallback) {
  const parsedValue = Number.parseInt(String(rawValue ?? ""), 10);
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : fallback;
}

function getRateLimitConfig() {
  return {
    windowMs: parsePositiveInt(process.env.BUNDLE_TRIGGER_RATE_LIMIT_WINDOW_MS, DEFAULT_RATE_LIMIT_WINDOW_MS),
    maxRequests: parsePositiveInt(process.env.BUNDLE_TRIGGER_RATE_LIMIT_MAX, DEFAULT_RATE_LIMIT_MAX),
  };
}

function getRepoProtectionConfig() {
  return {
    cooldownMs: parsePositiveInt(process.env.BUNDLE_TRIGGER_REPO_COOLDOWN_MS, DEFAULT_REPO_COOLDOWN_MS),
    activeJobTtlMs: parsePositiveInt(process.env.BUNDLE_TRIGGER_ACTIVE_JOB_TTL_MS, DEFAULT_ACTIVE_JOB_TTL_MS),
  };
}

function getClientIp(req) {
  const forwardedFor = req?.headers?.["x-forwarded-for"];
  if (typeof forwardedFor === "string" && forwardedFor.length > 0) {
    return forwardedFor.split(",")[0].trim();
  }

  const realIp = req?.headers?.["x-real-ip"];
  if (typeof realIp === "string" && realIp.length > 0) {
    return realIp.trim();
  }

  return req?.socket?.remoteAddress || "unknown";
}

function cleanupExpiredEntries(now = Date.now()) {
  const { windowMs } = getRateLimitConfig();
  const { cooldownMs, activeJobTtlMs } = getRepoProtectionConfig();

  for (const [ip, entry] of ipRateLimits.entries()) {
    if (now - entry.windowStart >= windowMs) {
      ipRateLimits.delete(ip);
    }
  }

  for (const [repo, nextAllowedAt] of repoCooldowns.entries()) {
    if (now >= nextAllowedAt + cooldownMs) {
      repoCooldowns.delete(repo);
    }
  }

  for (const [repo, job] of activeRepoJobs.entries()) {
    if (now - job.startedAt >= activeJobTtlMs) {
      activeRepoJobs.delete(repo);
    }
  }
}

function checkRateLimit(ip, now = Date.now()) {
  cleanupExpiredEntries(now);
  const { windowMs, maxRequests } = getRateLimitConfig();

  const existing = ipRateLimits.get(ip);
  if (!existing) {
    ipRateLimits.set(ip, { count: 1, windowStart: now });
    return { allowed: true, remaining: maxRequests - 1, retryAfterSeconds: 0 };
  }

  if (now - existing.windowStart >= windowMs) {
    ipRateLimits.set(ip, { count: 1, windowStart: now });
    return { allowed: true, remaining: maxRequests - 1, retryAfterSeconds: 0 };
  }

  if (existing.count >= maxRequests) {
    const retryAfterMs = windowMs - (now - existing.windowStart);
    const retryAfterSeconds = Math.max(1, Math.ceil(retryAfterMs / 1000));
    return { allowed: false, remaining: 0, retryAfterSeconds };
  }

  existing.count += 1;
  ipRateLimits.set(ip, existing);
  return { allowed: true, remaining: maxRequests - existing.count, retryAfterSeconds: 0 };
}

function checkRepoCooldown(repoKey, now = Date.now()) {
  cleanupExpiredEntries(now);
  const { cooldownMs } = getRepoProtectionConfig();

  const nextAllowedAt = repoCooldowns.get(repoKey);
  if (!nextAllowedAt || now >= nextAllowedAt) {
    return { allowed: true, retryAfterSeconds: 0 };
  }

  const retryAfterSeconds = Math.max(1, Math.ceil((nextAllowedAt - now) / 1000));
  return { allowed: false, retryAfterSeconds, cooldownMs };
}

function setRepoCooldown(repoKey, now = Date.now()) {
  const { cooldownMs } = getRepoProtectionConfig();
  repoCooldowns.set(repoKey, now + cooldownMs);
}

function getActiveRepoJob(repoKey, now = Date.now()) {
  cleanupExpiredEntries(now);
  return activeRepoJobs.get(repoKey) || null;
}

function markRepoJobActive(repoKey, runId = null, runUrl = null, now = Date.now()) {
  activeRepoJobs.set(repoKey, {
    startedAt: now,
    runId,
    runUrl,
  });
}

function clearRepoJob(repoKey) {
  activeRepoJobs.delete(repoKey);
}

function normalizeRepoKey(owner, repo) {
  return `${String(owner || "").toLowerCase()}/${String(repo || "").toLowerCase()}`;
}

function isAllowedOrigin(originHeader) {
  const allowListRaw = process.env.BUNDLE_TRIGGER_ALLOWED_ORIGINS;
  if (!allowListRaw || allowListRaw.trim().length === 0) {
    return true;
  }

  if (!originHeader || typeof originHeader !== "string") {
    return false;
  }

  const allowedOrigins = allowListRaw
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);

  return allowedOrigins.includes(originHeader);
}

function isAuthorizedRequest(req) {
  const expectedApiKey = process.env.BUNDLE_TRIGGER_API_KEY;
  if (!expectedApiKey) {
    return true;
  }

  const providedKey = req?.headers?.["x-bundle-trigger-key"];
  return typeof providedKey === "string" && providedKey === expectedApiKey;
}

function __resetSecurityStateForTests() {
  ipRateLimits.clear();
  repoCooldowns.clear();
  activeRepoJobs.clear();
}

export {
  checkRateLimit,
  checkRepoCooldown,
  clearRepoJob,
  getActiveRepoJob,
  getClientIp,
  isAllowedOrigin,
  isAuthorizedRequest,
  markRepoJobActive,
  normalizeRepoKey,
  setRepoCooldown,
  __resetSecurityStateForTests,
};