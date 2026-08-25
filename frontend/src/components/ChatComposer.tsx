import { useEffect, useRef, useState } from "react";
import type { LoadingState } from "../types/api";

export type ArtifactAction = "markdown" | "html" | "ship30";

interface ChatComposerProps {
  onSend: (content: string) => void;
  onArtifact: (action: ArtifactAction, instruction: string) => void;
  disabled: boolean;
  loading: LoadingState;
  placeholder?: string;
}

export function ChatComposer({
  onSend,
  onArtifact,
  disabled,
  loading,
  placeholder = "Ask about product growth, frameworks, or Lenny's guests…",
}: ChatComposerProps) {
  const [value, setValue] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [artifactMode, setArtifactMode] = useState<ArtifactAction | null>(null);
  const [artifactInstruction, setArtifactInstruction] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const isBusy = disabled || loading !== null;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || isBusy) return;
    onSend(trimmed);
    setValue("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  function openArtifactMode(mode: ArtifactAction) {
    setArtifactMode(mode);
    setMenuOpen(false);
    setArtifactInstruction("");
  }

  function submitArtifact(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = artifactInstruction.trim();
    if (!trimmed || !artifactMode || isBusy) return;
    onArtifact(artifactMode, trimmed);
    setArtifactMode(null);
    setArtifactInstruction("");
  }

  const artifactLabels: Record<ArtifactAction, string> = {
    markdown: "Create Markdown artifact",
    html: "Create HTML artifact",
    ship30: "Create Ship 30 essay",
  };

  return (
    <div className="composer">
      {artifactMode && (
        <form className="composer__artifact-form" onSubmit={submitArtifact}>
          <label htmlFor="artifact-instruction" className="composer__artifact-label">
            {artifactLabels[artifactMode]}
          </label>
          {artifactMode === "ship30" && (
            <p className="composer__artifact-hint">
              Generation may take a few minutes depending on the selected provider.
            </p>
          )}
          <textarea
            id="artifact-instruction"
            className="composer__textarea"
            value={artifactInstruction}
            onChange={(e) => setArtifactInstruction(e.target.value)}
            placeholder={
              artifactMode === "ship30"
                ? "Essay topic or angle…"
                : "Describe what to create…"
            }
            rows={3}
            autoFocus
          />
          <div className="composer__artifact-actions">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setArtifactMode(null)}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={isBusy || !artifactInstruction.trim()}
            >
              Generate
            </button>
          </div>
        </form>
      )}

      <form className="composer__form" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          className="composer__textarea"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={2}
          disabled={isBusy}
          aria-label="Message"
        />
        <div className="composer__toolbar">
          <div className="composer__menu" ref={menuRef}>
            <button
              type="button"
              className="btn btn--ghost btn--icon"
              onClick={() => setMenuOpen((o) => !o)}
              disabled={isBusy}
              aria-label="Create artifact"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
            {menuOpen && (
              <div className="composer__dropdown" role="menu">
                <button type="button" role="menuitem" onClick={() => openArtifactMode("ship30")}>
                  Ship 30 essay
                </button>
                <button type="button" role="menuitem" onClick={() => openArtifactMode("markdown")}>
                  Markdown artifact
                </button>
                <button type="button" role="menuitem" onClick={() => openArtifactMode("html")}>
                  HTML artifact
                </button>
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn btn--primary"
            disabled={isBusy || !value.trim()}
          >
            {loading === "sending-message" ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
