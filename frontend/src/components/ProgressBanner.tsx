import type { LoadingState } from "../types/api";
import { isArtifactLoading } from "../types/api";

const PROGRESS_COPY: Partial<Record<NonNullable<LoadingState>, string>> = {
  "creating-ship30":
    "Generating and validating a grounded Ship 30 essay…",
  "creating-artifact-markdown":
    "Generating and validating a grounded Markdown artifact…",
  "creating-artifact-html":
    "Generating and validating a grounded HTML artifact…",
};

interface ProgressBannerProps {
  loading: LoadingState;
  elapsedSeconds: number;
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}

export function ProgressBanner({
  loading,
  elapsedSeconds,
}: ProgressBannerProps) {
  if (!loading || !isArtifactLoading(loading)) {
    return null;
  }

  const label = PROGRESS_COPY[loading];

  return (
    <div className="progress-banner" role="status" aria-live="polite">
      <div className="progress-banner__inner">
        <span className="progress-banner__spinner" aria-hidden="true" />
        <div className="progress-banner__copy">
          <strong>{label}</strong>
          <span>
            Generation may take a few minutes depending on the selected
            provider. Elapsed {formatElapsed(elapsedSeconds)}.
          </span>
        </div>
      </div>
    </div>
  );
}

export function loadingMessageFor(state: NonNullable<LoadingState>): string {
  const messages: Record<NonNullable<LoadingState>, string> = {
    "creating-session": "Creating session…",
    "loading-sessions": "Loading conversations…",
    "loading-messages": "Loading conversation history…",
    "sending-message": "Searching knowledge base and generating answer…",
    "creating-artifact-markdown":
      "Generating and validating a grounded Markdown artifact…",
    "creating-artifact-html":
      "Generating and validating a grounded HTML artifact…",
    "creating-ship30":
      "Generating and validating a grounded Ship 30 essay…",
  };

  return messages[state];
}
