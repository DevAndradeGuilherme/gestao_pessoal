"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { apiFetch, type ApiRequestInit } from "./api/client";

let client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  );
}

export function getSupabase(): SupabaseClient | null {
  if (!isSupabaseConfigured()) return null;
  if (!client) {
    client = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
      { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } },
    );
  }
  return client;
}

/** Ponto único para chamadas autenticadas quando os recursos GP-04 forem publicados. */
export async function authenticatedApiFetch<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const supabase = getSupabase();
  const { data, error } = supabase
    ? await supabase.auth.getSession()
    : { data: { session: null }, error: null };
  if (error || !data.session?.access_token) {
    throw new Error("Entre na sua conta para acessar a API.");
  }
  return apiFetch<T>(path, { ...init, accessToken: data.session.access_token });
}
