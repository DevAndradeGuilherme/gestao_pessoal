"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getSupabase, isSupabaseConfigured } from "@/lib/auth";
import { browserTimezone } from "@/lib/time";
import { readDemoState, writeDemoState } from "@/lib/demo/store";
import type { DemoState } from "@/lib/demo/types";
import { AgendaView, TodayView, TasksView, RoutinesView, SettingsView } from "./workspace-views";
import {
  LiveAgendaView,
  LiveRoutinesView,
  LiveSettingsView,
  LiveTasksView,
  LiveTodayView,
} from "./live-views";

export type Section = "hoje" | "agenda" | "tarefas" | "rotinas" | "configuracoes";

const navigation: { id: Section; label: string; href: string; icon: string }[] = [
  { id: "hoje", label: "Hoje", href: "/", icon: "◫" },
  { id: "agenda", label: "Agenda", href: "/agenda", icon: "▦" },
  { id: "tarefas", label: "Tarefas", href: "/tarefas", icon: "☑" },
  { id: "rotinas", label: "Rotinas", href: "/rotinas", icon: "↻" },
  { id: "configuracoes", label: "Configurações", href: "/configuracoes", icon: "⚙" },
];

export function Workspace({ section }: { section: Section }) {
  const router = useRouter();
  const [access, setAccess] = useState<"checking" | "demo" | "authenticated" | "denied">(
    "checking",
  );
  const [state, setState] = useState<DemoState | null>(null);
  const [email, setEmail] = useState("");
  const [flash, setFlash] = useState("");
  const timezone = browserTimezone();
  const authLost = useCallback(() => setAccess("denied"), []);

  useEffect(() => {
    let active = true;
    if (!isSupabaseConfigured()) {
      queueMicrotask(() => {
        if (!active) return;
        if (sessionStorage.getItem("gp05-demo-access") === "1") {
          setState(readDemoState());
          setAccess("demo");
        } else setAccess("denied");
      });
      return () => {
        active = false;
      };
    }
    const supabase = getSupabase()!;
    supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error || !data.session) setAccess("denied");
      else {
        setEmail(data.session.user.email ?? "Minha conta");
        setAccess("authenticated");
      }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      if (!session) setAccess("denied");
    });
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  const save = useCallback((next: DemoState, message: string) => {
    try {
      writeDemoState(next);
      setState(next);
      setFlash(message);
    } catch {
      setFlash("Não foi possível salvar no navegador. Verifique o armazenamento disponível.");
    }
  }, []);

  async function leave() {
    if (access === "authenticated") {
      const { error } = await getSupabase()!.auth.signOut();
      if (error) {
        setFlash("Não foi possível sair. Tente novamente.");
        return;
      }
    } else sessionStorage.removeItem("gp05-demo-access");
    router.replace("/login");
  }

  if (access === "checking")
    return (
      <main className="loading-page" aria-live="polite">
        Carregando seu espaço…
      </main>
    );
  if (access === "denied")
    return (
      <main className="loading-page">
        <div className="access-card">
          <div className="brand-mark">
            g<span>.</span>
          </div>
          <h1>Bem-vindo ao seu espaço.</h1>
          <p>Entre para acessar seus dados ou explore o modo de demonstração.</p>
          <Link className="button primary" href="/login">
            Ir para o acesso
          </Link>
        </div>
      </main>
    );

  const demo = access === "demo";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-mark">
            g<span>.</span>
          </span>
          <span>
            gestão<span className="brand-soft"> pessoal</span>
          </span>
        </Link>
        <div className="sidebar-label">ESPAÇO DE TRABALHO</div>
        <nav aria-label="Navegação principal" className="side-nav">
          {navigation.map((item) => (
            <Link
              key={item.id}
              href={item.href}
              aria-current={section === item.id ? "page" : undefined}
              className={section === item.id ? "nav-link active" : "nav-link"}
            >
              <span aria-hidden="true" className="nav-icon">
                {item.icon}
              </span>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="profile-dot">{demo ? "D" : email.charAt(0).toUpperCase()}</div>
          <div className="profile-copy">
            <strong>{demo ? "Demonstração" : email}</strong>
            <small>{demo ? "Dados neste navegador" : "Conta conectada"}</small>
          </div>
          <button className="text-button" onClick={leave} aria-label="Sair">
            Sair
          </button>
        </div>
      </aside>
      <div className="main-column">
        <header className="mobile-header">
          <Link href="/" className="brand">
            <span className="brand-mark">
              g<span>.</span>
            </span>
            <span>gestão pessoal</span>
          </Link>
          <button className="text-button" onClick={leave}>
            Sair
          </button>
        </header>
        <nav aria-label="Navegação móvel" className="mobile-nav">
          {navigation.map((item) => (
            <Link
              key={item.id}
              href={item.href}
              aria-current={section === item.id ? "page" : undefined}
              className={section === item.id ? "active" : ""}
            >
              <span aria-hidden="true">{item.icon}</span>
              <small>{item.label}</small>
            </Link>
          ))}
        </nav>
        <main className="content">
          {demo && (
            <div className="demo-banner" role="status">
              <strong>Modo de demonstração</strong>
              <span>
                Os dados são exemplos locais deste navegador. Nenhuma alteração é enviada à API.
              </span>
            </div>
          )}
          {flash && (
            <div className="success-banner" role="status">
              {flash}
              <button onClick={() => setFlash("")} aria-label="Dispensar mensagem">
                ×
              </button>
            </div>
          )}
          {demo && state && (
            <>
              {section === "hoje" && <TodayView state={state} save={save} />}
              {section === "agenda" && <AgendaView state={state} save={save} />}
              {section === "tarefas" && <TasksView state={state} save={save} />}
              {section === "rotinas" && <RoutinesView state={state} save={save} />}
              {section === "configuracoes" && (
                <SettingsView state={state} save={save} email={email} />
              )}
            </>
          )}
          {!demo && (
            <>
              {section === "hoje" && (
                <LiveTodayView timezone={timezone} notify={setFlash} authLost={authLost} />
              )}
              {section === "agenda" && (
                <LiveAgendaView timezone={timezone} notify={setFlash} authLost={authLost} />
              )}
              {section === "tarefas" && (
                <LiveTasksView timezone={timezone} notify={setFlash} authLost={authLost} />
              )}
              {section === "rotinas" && (
                <LiveRoutinesView timezone={timezone} notify={setFlash} authLost={authLost} />
              )}
              {section === "configuracoes" && (
                <LiveSettingsView email={email} timezone={timezone} />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
