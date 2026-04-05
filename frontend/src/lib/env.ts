/**
 * Environment detection and API base URL configuration.
 *
 * - Web (browser dev): API proxied through Vite to 127.0.0.1:8000
 * - Web production: set VITE_API_URL to your deployed API
 * - Tauri desktop: API is a local Python sidecar on 127.0.0.1:8000
 * - Capacitor mobile: API is the cloud deployment (VITE_API_URL)
 */

export const IS_TAURI = typeof window !== "undefined" && "__TAURI__" in window;

export const IS_CAPACITOR =
  (typeof window !== "undefined" && window.location.protocol === "capacitor:") ||
  (typeof navigator !== "undefined" && /android|iphone|ipad/i.test(navigator.userAgent) && !IS_TAURI);

export const IS_DEV = import.meta.env.DEV;

/**
 * Get the API base URL depending on the runtime environment.
 *
 * Set VITE_API_URL in .env or .env.production for cloud deployment.
 * Defaults:
 *  - Desktop (Tauri) and browser dev: "" (relative, proxied or localhost)
 *  - Mobile (Capacitor) / Production: VITE_API_URL env var
 */
export function getApiBase(): string {
  // Explicit override always wins
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl;

  // Desktop or dev browser: local backend
  if (IS_TAURI || IS_DEV) return "";

  // Mobile / production: must be set via VITE_API_URL at build time
  console.warn(
    "[env] VITE_API_URL is not set. API calls may fail in production/mobile."
  );
  return "";
}
