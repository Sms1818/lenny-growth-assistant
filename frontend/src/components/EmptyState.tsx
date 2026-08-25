interface EmptyStateProps {
  onNewChat: () => void;
  onStarterPrompt: (prompt: string) => void;
  isCreating: boolean;
  backendUnavailable: boolean;
}

const STARTER_PROMPTS = [
  "How did Duolingo reignite growth?",
  "What does Elena Verna say about AI-era growth?",
  "Create a retention strategy brief",
  "Turn this conversation into a Ship 30 essay",
];

export function EmptyState({
  onNewChat,
  onStarterPrompt,
  isCreating,
  backendUnavailable,
}: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state__content">
        <p className="empty-state__eyebrow">Lenny Growth Assistant</p>
        <h2 className="empty-state__title">
          Grounded product and growth research
        </h2>
        <p className="empty-state__description">
          Ask questions grounded in Lenny&apos;s Podcast and Newsletter, follow up
          in the same session, inspect sources, and generate Ship 30 essays or
          Markdown/HTML artifacts.
        </p>

        {backendUnavailable && (
          <div className="banner banner--error" role="alert">
            Backend unavailable. Start the API server and refresh.
          </div>
        )}

        <button
          type="button"
          className="btn btn--primary"
          onClick={onNewChat}
          disabled={isCreating || backendUnavailable}
        >
          {isCreating ? "Creating session…" : "Start new chat"}
        </button>

        <div className="empty-state__starters">
          <span className="empty-state__starters-label">Try asking</span>
          <div className="empty-state__starter-grid">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="starter-chip"
                onClick={() => onStarterPrompt(prompt)}
                disabled={backendUnavailable || isCreating}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
