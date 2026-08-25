import type {
  ArtifactCreateRequest,
  ArtifactGenerationErrorDetail,
  ArtifactResponse,
  CreateArtifactResponse,
  HealthResponse,
  MessageCreateRequest,
  ProviderMode,
  SendMessageResponse,
  SessionCreateRequest,
  SessionListResponse,
  SessionMessagesResponse,
  SessionResponse,
  SessionUpdateRequest,
  Ship30ArtifactRequest,
} from "../types/api";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function formatErrorDetail(detail: unknown): string {
  if (detail == null) {
    return "An unexpected error occurred.";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (typeof detail === "object" && detail !== null) {
    const obj = detail as ArtifactGenerationErrorDetail & {
      detail?: unknown;
    };

    if (obj.message) {
      const parts = [obj.message];

      if (obj.grounding_issues?.length) {
        parts.push(
          `Grounding issues: ${obj.grounding_issues.map((i) => i.text).join("; ")}`,
        );
      }
      if (obj.validation_issues?.length) {
        parts.push(`Validation: ${obj.validation_issues.join("; ")}`);
      }
      if (obj.structure_issues?.length) {
        parts.push(`Structure: ${obj.structure_issues.join("; ")}`);
      }

      return parts.join(" ");
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            return String((item as { msg: string }).msg);
          }
          return JSON.stringify(item);
        })
        .join("; ");
    }
  }

  return "An unexpected error occurred.";
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "Unable to reach the backend. Check that the API server is running.",
    );
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      const body = await response.json();
      detail = body.detail ?? body;
    } catch {
      detail = response.statusText;
    }

    throw new ApiError(
      response.status,
      formatErrorDetail(detail),
      detail,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  listSessions(): Promise<SessionListResponse> {
    return request<SessionListResponse>("/sessions");
  },

  createSession(body: SessionCreateRequest = {}): Promise<SessionResponse> {
    return request<SessionResponse>("/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  updateSession(
    sessionId: string,
    body: SessionUpdateRequest,
  ): Promise<SessionResponse> {
    return request<SessionResponse>(`/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteSession(sessionId: string): Promise<void> {
    return request<void>(`/sessions/${sessionId}`, {
      method: "DELETE",
    });
  },

  listMessages(sessionId: string): Promise<SessionMessagesResponse> {
    return request<SessionMessagesResponse>(
      `/sessions/${sessionId}/messages`,
    );
  },

  sendMessage(
    sessionId: string,
    body: MessageCreateRequest,
  ): Promise<SendMessageResponse> {
    return request<SendMessageResponse>(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  createArtifact(
    sessionId: string,
    body: ArtifactCreateRequest,
  ): Promise<CreateArtifactResponse> {
    return request<CreateArtifactResponse>(
      `/sessions/${sessionId}/artifacts`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  },

  createShip30(
    sessionId: string,
    body: Ship30ArtifactRequest,
  ): Promise<CreateArtifactResponse> {
    return request<CreateArtifactResponse>(
      `/sessions/${sessionId}/artifacts/ship30`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  },

  getArtifact(artifactId: string): Promise<ArtifactResponse> {
    return request<ArtifactResponse>(`/artifacts/${artifactId}`);
  },
};

export type { ProviderMode };
