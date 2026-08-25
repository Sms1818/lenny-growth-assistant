import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatEntry } from "../types/api";
import { SourceList } from "./SourceList";

function formatModelMeta(provider: string | null, model: string | null): string | null {
  if (!provider && !model) return null;
  const parts: string[] = [];
  if (provider) parts.push(provider);
  if (model) parts.push(model);
  return parts.join(" · ");
}

interface ChatMessageProps {
  entry: ChatEntry;
  onOpenArtifact?: (messageId: string) => void;
  hasLinkedArtifact?: boolean;
}

export function ChatMessage({
  entry,
  onOpenArtifact,
  hasLinkedArtifact,
}: ChatMessageProps) {
  const { message, sources, pending, error } = entry;
  const isUser = message.role === "user";
  const modelMeta = !isUser ? formatModelMeta(message.model_provider, message.model_name) : null;

  return (
    <article
      className={`chat-message ${isUser ? "chat-message--user" : "chat-message--assistant"} ${pending ? "chat-message--pending" : ""}`}
      aria-busy={pending || undefined}
    >
      <header className="chat-message__header">
        <span className="chat-message__role">{isUser ? "You" : "Assistant"}</span>
        {modelMeta && (
          <span className="chat-message__meta">Used: {modelMeta}</span>
        )}
      </header>

      <div className="chat-message__body">
        {pending ? (
          <div className="chat-message__loading">
            <span className="spinner" aria-hidden="true" />
            <span>{message.content}</span>
          </div>
        ) : error ? (
          <p className="chat-message__error" role="alert">
            {error}
          </p>
        ) : isUser ? (
          <p className="chat-message__text">{message.content}</p>
        ) : (
          <div className="chat-message__markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {!isUser && sources && sources.length > 0 && !pending && (
        <SourceList sources={sources} />
      )}

      {hasLinkedArtifact && onOpenArtifact && !pending && (
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => onOpenArtifact(message.id)}
        >
          View artifact
        </button>
      )}
    </article>
  );
}
