import type { SourceResponse } from "../types/api";
import { useState } from "react";

function formatTimestampRange(
  start: string | null,
  end: string | null,
): string | null {
  if (!start && !end) return null;
  if (start && end) return `${start} – ${end}`;
  return start ?? end;
}

interface SourceListProps {
  sources: SourceResponse[];
}

export function SourceList({ sources }: SourceListProps) {
  const [expanded, setExpanded] = useState(true);

  if (sources.length === 0) return null;

  return (
    <div className="source-list">
      <button
        type="button"
        className="source-list__toggle"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <span>{sources.length} source{sources.length === 1 ? "" : "s"}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d={expanded ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"}
            stroke="currentColor"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </button>

      {expanded && (
        <ol className="source-list__items">
          {sources.map((source, index) => {
            const timestamp = formatTimestampRange(
              source.start_timestamp,
              source.end_timestamp,
            );
            const primaryUrl = source.youtube_url ?? source.source_url;

            return (
              <li key={source.chunk_id} className="source-card">
                <span className="source-card__index">{index + 1}</span>
                <div className="source-card__body">
                  <div className="source-card__title">{source.title}</div>
                  <div className="source-card__meta">
                    {source.source_type}
                    {source.guest ? ` · ${source.guest}` : ""}
                    {timestamp ? ` · ${timestamp}` : ""}
                  </div>
                  {primaryUrl && (
                    <a
                      href={primaryUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="source-card__link"
                    >
                      Open source
                    </a>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
