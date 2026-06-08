import { createClient, SupabaseClient } from "@supabase/supabase-js";

const DEFAULT_URL = "https://husyiuqyswpudlyuskno.supabase.co";
const DEFAULT_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1c3lpdXF5c3dwdWRseXVza25vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NDUwNDYsImV4cCI6MjA5NTIyMTA0Nn0.dNCRxdGlL5vgug0sB4BwhCfBx_nAt9oR0RT2Upv0al8";

let sharedClient: SupabaseClient | null = null;

/** Single Supabase client for realtime tunnels (avoids duplicate GoTrueClient warnings). */
export function getSupabaseClient(): SupabaseClient {
  if (sharedClient) return sharedClient;

  const url = import.meta.env.VITE_SUPABASE_URL || DEFAULT_URL;
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || DEFAULT_ANON_KEY;
  sharedClient = createClient(url, anonKey, {
    realtime: { params: { eventsPerSecond: 10 } },
  });
  return sharedClient;
}
