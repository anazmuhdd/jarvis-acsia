import type { Article } from "./api";

const CACHE_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours

interface NewsCacheEntry {
  articles: Article[];
  topics: string[];
  cachedAt: number;
  userId: string;
}

function getCacheKey(userId: string): string {
  return `news_cache_${userId}`;
}

/**
 * Derives a stable, safe cache key for a user.
 *
 * - Authenticated users  → MSAL homeAccountId (already unique per tenant/user)
 * - Guest / fallback     → base64 of "jobTitle|department" (best-effort)
 */
export function deriveUserId(
  msalHomeAccountId?: string,
  jobTitle?: string,
  department?: string,
): string {
  if (msalHomeAccountId) return msalHomeAccountId;
  // Sanitize so we never store raw PII as a plain string in a key
  const raw = `${jobTitle ?? "unknown"}|${department ?? "unknown"}`;
  try {
    return btoa(raw);
  } catch {
    return "guest";
  }
}

/** Returns cached articles if they exist and are still fresh (< 2 h old). */
export function getCachedNews(userId: string): NewsCacheEntry | null {
  try {
    const key = getCacheKey(userId);
    const raw = localStorage.getItem(key);
    if (!raw) return null;

    const entry: NewsCacheEntry = JSON.parse(raw);
    if (Date.now() - entry.cachedAt > CACHE_TTL_MS) {
      localStorage.removeItem(key); // evict stale entry
      return null;
    }

    return entry;
  } catch {
    return null;
  }
}

/** Stores articles and topics in localStorage for this user. */
export function setCachedNews(
  userId: string,
  articles: Article[],
  topics: string[],
): void {
  try {
    const entry: NewsCacheEntry = {
      articles,
      topics,
      cachedAt: Date.now(),
      userId,
    };
    localStorage.setItem(getCacheKey(userId), JSON.stringify(entry));
  } catch (e) {
    // Quota exceeded or private-browsing restriction – fail silently
    console.warn("News cache write failed:", e);
  }
}

/** Removes the cache entry for a user (e.g. on manual refresh). */
export function clearCachedNews(userId: string): void {
  try {
    localStorage.removeItem(getCacheKey(userId));
  } catch {
    // ignore
  }
}

/** Returns how many minutes remain until the cached result expires, or 0. */
export function cacheAgeMinutes(userId: string): number {
  try {
    const raw = localStorage.getItem(getCacheKey(userId));
    if (!raw) return 0;
    const { cachedAt } = JSON.parse(raw) as NewsCacheEntry;
    const remainingMs = CACHE_TTL_MS - (Date.now() - cachedAt);
    return Math.max(0, Math.floor(remainingMs / 60_000));
  } catch {
    return 0;
  }
}
