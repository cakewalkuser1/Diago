/**
 * Supabase client for authentication and user management.
 *
 * Configured via VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.
 * Use the NEW publishable key (sb_publishable_...) from Supabase Dashboard → Settings → API.
 * Do not use the legacy anon JWT or the new secret key (sb_secret_...) here—never expose the secret in the frontend.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

if (SUPABASE_ANON_KEY && SUPABASE_ANON_KEY.startsWith("sb_secret_")) {
  console.error(
    "[Supabase] You are using the SECRET key in the frontend. Use the PUBLISHABLE key (sb_publishable_...) in VITE_SUPABASE_ANON_KEY. Get it from Dashboard → Settings → API."
  );
}

/** Whether Supabase auth is configured and available */
export const isAuthEnabled = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

/** Supabase client (null if auth is not configured) */
export const supabase: SupabaseClient | null = isAuthEnabled
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null;

/**
 * Get the current session's access token for API calls.
 * Returns null if not authenticated or auth is not configured.
 */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
