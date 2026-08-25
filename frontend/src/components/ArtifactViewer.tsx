import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { marked } from "marked";
import type { ArtifactResponse } from "../types/api";

interface ArtifactViewerProps {
  artifact: ArtifactResponse;
  onClose: () => void;
}

function openBlobHtml(html: string) {
  const blob = new Blob(
    [html],
    {
      type: "text/html;charset=utf-8",
    },
  );

  const url = URL.createObjectURL(blob);

  const opened = window.open(
    url,
    "_blank",
    "noopener,noreferrer",
  );

  if (!opened) {
    URL.revokeObjectURL(url);
    return;
  }

  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 5 * 60_000);
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function openArtifactInNewTab(
  artifact: ArtifactResponse,
) {
  if (artifact.artifact_type === "html") {
    openBlobHtml(artifact.content);
    return;
  }

  const renderedMarkdown = marked.parse(
    artifact.content,
  );

  const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  />
  <title>${escapeHtml(artifact.title)}</title>
  <style>
    :root {
      font-family:
        Inter,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
      color: #202124;
      background: #ffffff;
    }

    body {
      margin: 0;
      padding: 48px 24px 80px;
    }

    main {
      max-width: 820px;
      margin: 0 auto;
      line-height: 1.7;
      font-size: 17px;
    }

    h1,
    h2,
    h3 {
      line-height: 1.25;
      margin-top: 1.8em;
    }

    h1 {
      font-size: 2.4rem;
      margin-top: 0;
    }

    h2 {
      font-size: 1.65rem;
    }

    h3 {
      font-size: 1.3rem;
    }

    p,
    li {
      margin-bottom: 0.8em;
    }

    blockquote {
      margin: 1.5em 0;
      padding: 0.1em 1em;
      border-left: 4px solid #dadce0;
      color: #5f6368;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin: 1.5em 0;
    }

    th,
    td {
      border: 1px solid #dadce0;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }

    th {
      background: #f8f9fa;
    }

    code {
      background: #f1f3f4;
      padding: 0.15em 0.35em;
      border-radius: 4px;
    }

    pre {
      overflow-x: auto;
      padding: 16px;
      background: #f1f3f4;
      border-radius: 8px;
    }

    pre code {
      padding: 0;
      background: transparent;
    }

    a {
      color: inherit;
    }
  </style>
</head>
<body>
  <main>
    ${renderedMarkdown}
  </main>
</body>
</html>`;

  openBlobHtml(html);
}

export function ArtifactViewer({
  artifact,
  onClose,
}: ArtifactViewerProps) {
  const typeLabel =
    artifact.artifact_type === "html"
      ? "HTML"
      : artifact.artifact_type === "markdown"
        ? "Markdown"
        : artifact.artifact_type;

  return (
    <aside
      className="artifact-viewer"
      aria-label="Artifact viewer"
    >
      <header className="artifact-viewer__header">
        <div className="artifact-viewer__title-group">
          <h2 className="artifact-viewer__title">
            {artifact.title}
          </h2>
          <span className="artifact-viewer__type">
            {typeLabel}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => openArtifactInNewTab(artifact)}
          >
            Open in new tab ↗
          </button>

          <button
            type="button"
            className="btn btn--ghost btn--icon"
            onClick={onClose}
            aria-label="Close artifact viewer"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </header>

      <div className="artifact-viewer__content">
        {artifact.artifact_type === "html" ? (
          <iframe
            sandbox=""
            srcDoc={artifact.content}
            title={artifact.title}
            className="artifact-viewer__iframe"
          />
        ) : (
          <div className="artifact-viewer__markdown prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {artifact.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </aside>
  );
}
