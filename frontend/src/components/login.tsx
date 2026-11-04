"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { getSupabase, isSupabaseConfigured } from "@/lib/auth";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const { error: authError } = await getSupabase()!.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (authError) setError("Não foi possível entrar. Confira seu e-mail e senha.");
    else window.location.assign("/");
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="brand-mark">g<span>.</span></div>
        <p className="eyebrow">SEU ESPAÇO PESSOAL</p>
        <h1>Organize o que importa.</h1>
        <p className="muted">Compromissos, tarefas e rotinas em um lugar tranquilo para o seu dia.</p>
        {isSupabaseConfigured() ? (
          <form onSubmit={submit} className="form-stack">
            <label>E-mail<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
            <label>Senha<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            {error && <p role="alert" className="error-box">{error}</p>}
            <button className="button primary" disabled={busy}>{busy ? "Entrando…" : "Entrar"}</button>
          </form>
        ) : (
          <div className="notice">
            <strong>Autenticação ainda não configurada</strong>
            <p>Configure as variáveis públicas do Supabase para entrar com sua conta. Você pode explorar a demonstração local sem usar dados reais.</p>
            <button className="button primary" onClick={() => { sessionStorage.setItem("gp05-demo-access", "1"); window.location.assign("/"); }}>Explorar demonstração</button>
          </div>
        )}
        <Link className="subtle-link" href="/">Voltar ao início</Link>
      </div>
    </main>
  );
}
