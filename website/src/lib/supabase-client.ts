import { createClient, SupabaseClient } from "@supabase/supabase-js";

let sharedClient: SupabaseClient | null = null;

/** Single Supabase client for realtime tunnels (avoids duplicate GoTrueClient warnings). */
export function getSupabaseClient(): SupabaseClient {
  if (sharedClient) return sharedClient;

  const url = import.meta.env.VITE_SUPABASE_URL;
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
  
  if (!url || !anonKey) {
    throw new Error("Missing Supabase environment variables: VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY");
  }
  sharedClient = createClient(url, anonKey, {
    realtime: { params: { eventsPerSecond: 10 } },
  });
  return sharedClient;
}
