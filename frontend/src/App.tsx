import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import { ArtifactViewer } from "./components/ArtifactViewer";
import { ChatComposer, type ArtifactAction } from "./components/ChatComposer";
import { ChatMessage } from "./components/ChatMessage";
import { EmptyState } from "./components/EmptyState";
import {
  loadingMessageFor,
  ProgressBanner,
} from "./components/ProgressBanner";
import { ProviderSelector } from "./components/ProviderSelector";
import { SessionSidebar } from "./components/SessionSidebar";
import type {
  ArtifactResponse,
  ChatEntry,
  LoadingState,
  MessageWithSourcesResponse,
  ProviderMode,
  SessionResponse,
} from "./types/api";
import {
  isArtifactLoading,
  sessionDisplayTitle,
} from "./types/api";
import "./index.css";

function pendingMessage(content: string, role: "user" | "assistant"): ChatEntry {
  return {
    id: `pending-${role}-${Date.now()}-${Math.random()}`,
    message: {
      id: `pending-${role}`,
      session_id: "",
      sequence_number: 0,
      role,
      content,
      model_provider: null,
      model_name: null,
      source_chunk_ids: null,
      created_at: new Date().toISOString(),
    },
    pending: true,
  };
}

function isUntitledSession(
  value: SessionResponse | null,
): boolean {
  if (!value?.title) return true;

  return value.title.trim().toLowerCase() === "new conversation";
}

function formatApiError(err: unknown, fallback: string): string {
  if (!(err instanceof ApiError)) return fallback;
  if (err.status === 0) {
    return "Unable to reach the backend. Check that the API server is running.";
  }
  if (err.status === 503) return err.message;
  if (err.status === 504) {
    return "Generation timed out. Try again or switch provider mode.";
  }
  if (err.status === 422) return err.message;
  return err.message || fallback;
}

export default function App() {
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [messagesBySession, setMessagesBySession] = useState<
    Record<string, ChatEntry[]>
  >({});
  const [artifactsBySession, setArtifactsBySession] = useState<
    Record<string, Record<string, ArtifactResponse>>
  >({});
  const [artifactMessageMap, setArtifactMessageMap] = useState<
    Record<string, string>
  >({});
  const [activeArtifact, setActiveArtifact] = useState<ArtifactResponse | null>(
    null,
  );
  const [artifactOpen, setArtifactOpen] = useState(false);
  const [loading, setLoading] = useState<LoadingState>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [providerMode, setProviderMode] = useState<ProviderMode>("auto");
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [generationElapsed, setGenerationElapsed] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const generationTimerRef = useRef<number | null>(null);

  const messages = session ? (messagesBySession[session.id] ?? []) : [];

  const hydrateSessionMessages = useCallback(
    async (sessionId: string) => {
      const response = await api.listMessages(sessionId);
      const entries: ChatEntry[] = response.messages.map(
        (message: MessageWithSourcesResponse) => ({
          id: message.id,
          message,
          sources: message.sources,
        }),
      );

      const artifacts: Record<string, ArtifactResponse> = {};
      const messageMap: Record<string, string> = {};

      const artifactIds = response.messages
        .filter((message) => message.artifact_id)
        .map((message) => ({
          messageId: message.id,
          artifactId: message.artifact_id as string,
        }));

      await Promise.all(
        artifactIds.map(async ({ messageId, artifactId }) => {
          try {
            const artifact = await api.getArtifact(artifactId);
            artifacts[artifactId] = artifact;
            messageMap[messageId] = artifactId;
          } catch {
            // Artifact may have been removed; skip silently.
          }
        }),
      );

      setMessagesBySession((prev) => ({
        ...prev,
        [sessionId]: entries,
      }));
      setArtifactsBySession((prev) => ({
        ...prev,
        [sessionId]: artifacts,
      }));
      setArtifactMessageMap((prev) => ({
        ...prev,
        ...messageMap,
      }));
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading("loading-sessions");
      try {
        await api.health();
        if (cancelled) return;
        setBackendOk(true);

        const { sessions: loadedSessions } = await api.listSessions();
        if (cancelled) return;

        setSessions(loadedSessions);

        if (loadedSessions.length > 0) {
          const first = loadedSessions[0];
          setSession(first);
          setLoading("loading-messages");
          await hydrateSessionMessages(first.id);
        }
      } catch {
        if (!cancelled) setBackendOk(false);
      } finally {
        if (!cancelled) setLoading(null);
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [hydrateSessionMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (isArtifactLoading(loading)) {
      setGenerationElapsed(0);
      generationTimerRef.current = window.setInterval(() => {
        setGenerationElapsed((seconds) => seconds + 1);
      }, 1000);
    } else {
      if (generationTimerRef.current) {
        clearInterval(generationTimerRef.current);
        generationTimerRef.current = null;
      }
      setGenerationElapsed(0);
    }

    return () => {
      if (generationTimerRef.current) {
        clearInterval(generationTimerRef.current);
      }
    };
  }, [loading]);

  const updateMessages = useCallback(
    (sessionId: string, updater: (prev: ChatEntry[]) => ChatEntry[]) => {
      setMessagesBySession((prev) => ({
        ...prev,
        [sessionId]: updater(prev[sessionId] ?? []),
      }));
    },
    [],
  );

  const handleNewChat = useCallback(async () => {
    setGlobalError(null);

    if (
      session &&
      isUntitledSession(session) &&
      (messagesBySession[session.id]?.length ?? 0) === 0
    ) {
      setActiveArtifact(null);
      setArtifactOpen(false);
      setMobileSidebarOpen(false);
      return;
    }

    setLoading("creating-session");
    setActiveArtifact(null);
    setArtifactOpen(false);

    try {
      const newSession = await api.createSession();
      setSession(newSession);
      setSessions((prev) => [
        newSession,
        ...prev.filter((item) => item.id !== newSession.id),
      ]);
      setMessagesBySession((prev) => ({ ...prev, [newSession.id]: [] }));
      setMobileSidebarOpen(false);
    } catch (err) {
      setGlobalError(formatApiError(err, "Failed to create session."));
    } finally {
      setLoading(null);
    }
  }, [session, messagesBySession]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      const selected = sessions.find((item) => item.id === sessionId);
      if (!selected) return;

      setSession(selected);
      setActiveArtifact(null);
      setArtifactOpen(false);
      setGlobalError(null);
      setMobileSidebarOpen(false);

      if (messagesBySession[sessionId]) return;

      setLoading("loading-messages");
      try {
        await hydrateSessionMessages(sessionId);
      } catch (err) {
        setGlobalError(
          formatApiError(err, "Failed to load conversation history."),
        );
      } finally {
        setLoading(null);
      }
    },
    [sessions, messagesBySession, hydrateSessionMessages],
  );

  const ensureSession = useCallback(async (): Promise<SessionResponse | null> => {
    if (session) return session;

    setLoading("creating-session");
    try {
      const newSession = await api.createSession();
      setSession(newSession);
      setSessions((prev) => [
        newSession,
        ...prev.filter((item) => item.id !== newSession.id),
      ]);
      setMessagesBySession((prev) => ({ ...prev, [newSession.id]: [] }));
      return newSession;
    } catch (err) {
      setGlobalError(formatApiError(err, "Failed to create session."));
      return null;
    } finally {
      setLoading(null);
    }
  }, [session]);

  const handleSend = useCallback(
    async (content: string) => {
      setGlobalError(null);
      const currentSession = await ensureSession();
      if (!currentSession) return;

      const sessionId = currentSession.id;
      const userPending = pendingMessage(content, "user");
      const assistantPending = pendingMessage(
        loadingMessageFor("sending-message"),
        "assistant",
      );

      updateMessages(sessionId, (prev) => [
        ...prev,
        userPending,
        assistantPending,
      ]);
      setLoading("sending-message");

      try {
        const response = await api.sendMessage(sessionId, {
          content,
          provider_mode: providerMode,
        });

        updateMessages(sessionId, (prev) => {
          const withoutPending = prev.filter((entry) => !entry.pending);
          return [
            ...withoutPending,
            {
              id: response.user_message.id,
              message: response.user_message,
            },
            {
              id: response.assistant_message.id,
              message: response.assistant_message,
              sources: response.sources,
            },
          ];
        });

        if (isUntitledSession(currentSession)) {
          const { sessions: refreshedSessions } =
            await api.listSessions();

          setSessions(refreshedSessions);

          const refreshedSession =
            refreshedSessions.find(
              (item) => item.id === sessionId,
            );

          if (refreshedSession) {
            setSession(refreshedSession);
          }
        }
      } catch (err) {
        updateMessages(sessionId, (prev) => {
          const withoutPending = prev.filter((entry) => !entry.pending);
          return [
            ...withoutPending,
            {
              id: userPending.id,
              message: { ...userPending.message, session_id: sessionId },
            },
            {
              id: `error-${Date.now()}`,
              message: {
                ...assistantPending.message,
                session_id: sessionId,
                content: "Unable to generate a response.",
              },
              error: formatApiError(err, "Failed to send message."),
            },
          ];
        });
      } finally {
        setLoading(null);
      }
    },
    [ensureSession, updateMessages, providerMode],
  );

  const handleArtifact = useCallback(
    async (action: ArtifactAction, instruction: string) => {
      setGlobalError(null);
      const currentSession = await ensureSession();
      if (!currentSession) return;

      const sessionId = currentSession.id;
      const loadingState: LoadingState =
        action === "ship30"
          ? "creating-ship30"
          : action === "html"
            ? "creating-artifact-html"
            : "creating-artifact-markdown";

      const userLabel =
        action === "ship30"
          ? `Create Ship 30 essay: ${instruction}`
          : `Create ${action} artifact: ${instruction}`;

      const userPending = pendingMessage(userLabel, "user");
      const assistantPending = pendingMessage(
        loadingMessageFor(loadingState),
        "assistant",
      );

      updateMessages(sessionId, (prev) => [
        ...prev,
        userPending,
        assistantPending,
      ]);
      setLoading(loadingState);

      try {
        const response =
          action === "ship30"
            ? await api.createShip30(sessionId, {
                topic: instruction,
                provider_mode: providerMode,
              })
            : await api.createArtifact(sessionId, {
                artifact_type: action,
                instruction,
                provider_mode: providerMode,
              });

        updateMessages(sessionId, (prev) => {
          const withoutPending = prev.filter((entry) => !entry.pending);
          return [
            ...withoutPending,
            {
              id: response.user_message.id,
              message: response.user_message,
            },
            {
              id: response.assistant_message.id,
              message: response.assistant_message,
              sources: response.sources,
            },
          ];
        });

        setArtifactsBySession((prev) => ({
          ...prev,
          [sessionId]: {
            ...(prev[sessionId] ?? {}),
            [response.artifact.id]: response.artifact,
          },
        }));
        setArtifactMessageMap((prev) => ({
          ...prev,
          [response.assistant_message.id]: response.artifact.id,
        }));
        setActiveArtifact(response.artifact);
        setArtifactOpen(true);
      } catch (err) {
        updateMessages(sessionId, (prev) => {
          const withoutPending = prev.filter((entry) => !entry.pending);
          return [
            ...withoutPending,
            {
              id: userPending.id,
              message: { ...userPending.message, session_id: sessionId },
            },
            {
              id: `error-${Date.now()}`,
              message: {
                ...assistantPending.message,
                session_id: sessionId,
                content: "Artifact generation failed.",
              },
              error: formatApiError(err, "Failed to create artifact."),
            },
          ];
        });
      } finally {
        setLoading(null);
      }
    },
    [ensureSession, updateMessages, providerMode],
  );

  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      const target = sessions.find(
        (item) => item.id === sessionId,
      );

      if (!target) return;

      const title = sessionDisplayTitle(target);

      if (
        !window.confirm(
          `Delete "${title}"? This conversation and its artifacts will be permanently removed.`,
        )
      ) {
        return;
      }

      setGlobalError(null);
      setDeletingSessionId(sessionId);

      try {
        await api.deleteSession(sessionId);

        const remaining = sessions.filter(
          (item) => item.id !== sessionId,
        );

        setSessions(remaining);

        setMessagesBySession((prev) => {
          const next = { ...prev };
          delete next[sessionId];
          return next;
        });

        setArtifactsBySession((prev) => {
          const next = { ...prev };
          delete next[sessionId];
          return next;
        });

        if (session?.id === sessionId) {
          setActiveArtifact(null);
          setArtifactOpen(false);

          const nextSession = remaining[0] ?? null;
          setSession(nextSession);

          if (
            nextSession &&
            !messagesBySession[nextSession.id]
          ) {
            setLoading("loading-messages");

            try {
              await hydrateSessionMessages(
                nextSession.id,
              );
            } finally {
              setLoading(null);
            }
          }
        }
      } catch (err) {
        setGlobalError(
          formatApiError(
            err,
            "Failed to delete conversation.",
          ),
        );
      } finally {
        setDeletingSessionId(null);
      }
    },
    [
      sessions,
      session,
      messagesBySession,
      hydrateSessionMessages,
    ],
  );

  const handleOpenArtifact = useCallback(
    async (messageId: string) => {
      if (!session) return;

      const artifactId = artifactMessageMap[messageId];
      if (!artifactId) return;

      let artifact = artifactsBySession[session.id]?.[artifactId];

      if (!artifact) {
        try {
          artifact = await api.getArtifact(artifactId);
          setArtifactsBySession((prev) => ({
            ...prev,
            [session.id]: {
              ...(prev[session.id] ?? {}),
              [artifactId]: artifact as ArtifactResponse,
            },
          }));
        } catch (err) {
          setGlobalError(formatApiError(err, "Failed to load artifact."));
          return;
        }
      }

      setActiveArtifact(artifact);
      setArtifactOpen(true);
    },
    [artifactMessageMap, artifactsBySession, session],
  );

  const showEmpty =
    !session &&
    messages.length === 0 &&
    loading !== "loading-sessions" &&
    loading !== "loading-messages";

  const isBusy = loading !== null;

  return (
    <div className="app">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={session?.id ?? null}
        onNewChat={handleNewChat}
        onSelectSession={(sessionId) => {
          void handleSelectSession(sessionId);
        }}
        onDeleteSession={(sessionId) => {
          void handleDeleteSession(sessionId);
        }}
        deletingSessionId={deletingSessionId}
        isCreating={loading === "creating-session"}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((value) => !value)}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />

      <main className="main">
        <header className="main__header">
          <button
            type="button"
            className="btn btn--ghost btn--icon mobile-menu-btn"
            onClick={() => setMobileSidebarOpen(true)}
            aria-label="Open menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>

          <div className="main__heading">
            <h1 className="main__title">{sessionDisplayTitle(session)}</h1>
          </div>

          <div className="main__controls">
            <ProviderSelector
              value={providerMode}
              onChange={setProviderMode}
              disabled={isBusy || backendOk === false}
            />
            {backendOk === false && (
              <span className="status-badge status-badge--error">Offline</span>
            )}
            {backendOk === true && (
              <span className="status-badge status-badge--ok">Connected</span>
            )}
          </div>
        </header>

        {globalError && (
          <div className="banner banner--error" role="alert">
            {globalError}
          </div>
        )}

        <ProgressBanner
          loading={loading}
          elapsedSeconds={generationElapsed}
        />

        <div className={`main__body ${artifactOpen ? "main__body--with-artifact" : ""}`}>
          <section className="chat-panel" aria-label="Chat">
            {showEmpty ? (
              <EmptyState
                onNewChat={handleNewChat}
                onStarterPrompt={(prompt) => {
                  void handleSend(prompt);
                }}
                isCreating={loading === "creating-session"}
                backendUnavailable={backendOk === false}
              />
            ) : (
              <div className="chat-panel__messages">
                {loading === "loading-messages" && messages.length === 0 && (
                  <p className="chat-panel__hint">Loading conversation…</p>
                )}

                {session &&
                  messages.length === 0 &&
                  loading !== "loading-messages" &&
                  !loading && (
                    <p className="chat-panel__hint">
                      Ask a grounded question or create an artifact from the
                      composer.
                    </p>
                  )}

                {messages.map((entry) => (
                  <ChatMessage
                    key={entry.id}
                    entry={entry}
                    hasLinkedArtifact={!!artifactMessageMap[entry.message.id]}
                    onOpenArtifact={(messageId) => {
                      void handleOpenArtifact(messageId);
                    }}
                  />
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}

            {!showEmpty && (
              <ChatComposer
                onSend={handleSend}
                onArtifact={handleArtifact}
                disabled={backendOk === false}
                loading={loading}
              />
            )}
          </section>

          {artifactOpen && activeArtifact && (
            <ArtifactViewer
              artifact={activeArtifact}
              onClose={() => setArtifactOpen(false)}
            />
          )}
        </div>
      </main>
    </div>
  );
}
