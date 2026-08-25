import type { SessionResponse } from "../types/api";
import { sessionDisplayTitle } from "../types/api";

interface SessionSidebarProps {
  sessions: SessionResponse[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  deletingSessionId: string | null;
  isCreating: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

function formatSessionSubtitle(session: SessionResponse): string {
  const date = new Date(session.updated_at || session.created_at);

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  deletingSessionId,
  isCreating,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onMobileClose,
}: SessionSidebarProps) {
  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close menu"
          onClick={onMobileClose}
        />
      )}

      <nav
        className={`sidebar ${collapsed ? "sidebar--collapsed" : ""} ${
          mobileOpen ? "sidebar--mobile-open" : ""
        }`}
        aria-label="Session navigation"
      >
        <div className="sidebar__brand">
          {!collapsed && (
            <div className="sidebar__identity">
              <span className="sidebar__product">
                Lenny Growth Assistant
              </span>
              <span className="sidebar__tagline">
                Research workspace
              </span>
            </div>
          )}

          <button
            type="button"
            className="btn btn--ghost btn--icon sidebar__collapse-btn"
            onClick={onToggleCollapse}
            aria-label={
              collapsed ? "Expand sidebar" : "Collapse sidebar"
            }
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              {collapsed ? (
                <path
                  d="M9 6l6 6-6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              ) : (
                <path
                  d="M15 6l-6 6 6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              )}
            </svg>
          </button>
        </div>

        <button
          type="button"
          className="btn btn--primary sidebar__new-chat"
          onClick={onNewChat}
          disabled={isCreating}
        >
          {isCreating ? "Creating…" : "New chat"}
        </button>

        {!collapsed && (
          <div className="sidebar__section">
            <h3 className="sidebar__section-title">
              Conversations
            </h3>

            {sessions.length > 0 ? (
              <ul className="sidebar__sessions">
                {sessions.map((item) => {
                  const title = sessionDisplayTitle(item);
                  const deleting =
                    deletingSessionId === item.id;

                  return (
                    <li
                      key={item.id}
                      className="sidebar__session-item"
                    >
                      <button
                        type="button"
                        className={`sidebar__session-btn ${
                          item.id === activeSessionId
                            ? "sidebar__session-btn--active"
                            : ""
                        }`}
                        onClick={() =>
                          onSelectSession(item.id)
                        }
                      >
                        <span className="sidebar__session-label">
                          {title}
                        </span>
                        <span className="sidebar__session-meta">
                          {formatSessionSubtitle(item)}
                        </span>
                      </button>

                      <button
                        type="button"
                        className="btn btn--ghost btn--icon sidebar__session-delete"
                        aria-label={`Delete conversation ${title}`}
                        title="Delete conversation"
                        disabled={deleting}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteSession(item.id);
                        }}
                      >
                        {deleting ? (
                          "…"
                        ) : (
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            aria-hidden="true"
                          >
                            <path
                              d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5M14 11v5"
                              stroke="currentColor"
                              strokeWidth="1.7"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="sidebar__empty">
                No conversations yet
              </p>
            )}
          </div>
        )}
      </nav>
    </>
  );
}
