"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authenticatedApiFetch, getSupabase, isSupabaseConfigured } from "@/lib/auth";
import { ApiError } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";
import { readDemoState, writeDemoState } from "@/lib/demo/store";
import type { DemoState } from "@/lib/demo/types";
import { AgendaView, TodayView, TasksView, RoutinesView, SettingsView } from "./workspace-views";

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
  const [apiHealth, setApiHealth] = useState<"checking" | "ok" | "error" | "unauthenticated">(
    "checking",
  );

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
        authenticatedApiFetch<HealthResponse>("/health")
          .then(() => {
            if (active) setApiHealth("ok");
          })
          .catch((requestError: unknown) => {
            if (!active) return;
            setApiHealth(
              requestError instanceof ApiError && requestError.body.code === "unauthenticated"
                ? "unauthenticated"
                : "error",
            );
          });
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
          {demo ? (
            <div className="demo-banner" role="status">
              <strong>Modo de demonstração</strong>
              <span>
                Os dados são exemplos locais deste navegador. Nenhuma alteração é enviada à API.
              </span>
            </div>
          ) : (
            <div className="demo-banner" role="status">
              <strong>API de domínio pendente</strong>
              <span>
                Sua sessão está ativa, mas GP-04 ainda não publicou os contratos dos recursos. Os
                dados pessoais não são exibidos aqui.
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
          {demo && state ? (
            <>
              {section === "hoje" && <TodayView state={state} save={save} />}
              {section === "agenda" && <AgendaView state={state} save={save} />}
              {section === "tarefas" && <TasksView state={state} save={save} />}
              {section === "rotinas" && <RoutinesView state={state} save={save} />}
              {section === "configuracoes" && (
                <SettingsView state={state} save={save} email={email} />
              )}
            </>
          ) : (
            <section className="empty-large">
              <span className="empty-icon">◌</span>
              <h1>{navigation.find((item) => item.id === section)?.label}</h1>
              <p>
                A integração com os dados reais estará disponível após a publicação das rotas e
                schemas de GP-04.
              </p>
              <p
                className="muted"
                role={apiHealth === "error" || apiHealth === "unauthenticated" ? "alert" : "status"}
              >
                {apiHealth === "checking"
                  ? "Verificando conexão com o FastAPI…"
                  : apiHealth === "ok"
                    ? "FastAPI acessível. Os recursos de domínio ainda não estão publicados."
                    : apiHealth === "unauthenticated"
                      ? "A sessão não foi aceita pela API. Entre novamente quando GP-03 publicar a validação do token."
                      : "Não foi possível conectar ao FastAPI. Confira a URL da API e tente novamente mais tarde."}
              </p>
              <Link className="button secondary" href="/configuracoes">
                Ver configurações
              </Link>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
