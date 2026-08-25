export type ProviderMode = "auto" | "local" | "cloud";

export interface SessionCreateRequest {
  title?: string | null;
  user_metadata?: Record<string, unknown> | null;
}

export interface SessionUpdateRequest {
  title: string;
}

export interface SessionResponse {
  id: string;
  title: string | null;
  user_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionResponse[];
}

export interface MessageCreateRequest {
  content: string;
  provider_mode?: ProviderMode | null;
}

export interface SourceResponse {
  chunk_id: number;
  title: string;
  source_type: string;
  guest: string | null;
  source_url: string | null;
  youtube_url: string | null;
  start_timestamp: string | null;
  end_timestamp: string | null;
}

export interface MessageResponse {
  id: string;
  session_id: string;
  sequence_number: number;
  role: string;
  content: string;
  model_provider: string | null;
  model_name: string | null;
  source_chunk_ids: string[] | null;
  created_at: string;
}

export interface MessageWithSourcesResponse extends MessageResponse {
  sources: SourceResponse[];
  artifact_id: string | null;
}

export interface SessionMessagesResponse {
  messages: MessageWithSourcesResponse[];
}

export interface SendMessageResponse {
  user_message: MessageResponse;
  assistant_message: MessageResponse;
  sources: SourceResponse[];
  provider_mode?: ProviderMode | null;
}

export interface ArtifactCreateRequest {
  artifact_type: "markdown" | "html";
  instruction: string;
  provider_mode?: ProviderMode | null;
}

export interface Ship30ArtifactRequest {
  topic: string;
  provider_mode?: ProviderMode | null;
}

export interface ArtifactResponse {
  id: string;
  message_id: string;
  title: string;
  artifact_type: string;
  content: string;
  created_at: string;
}

export interface CreateArtifactResponse {
  user_message: MessageResponse;
  assistant_message: MessageResponse;
  artifact: ArtifactResponse;
  sources: SourceResponse[];
  provider_mode?: ProviderMode | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
}

export interface ArtifactGenerationErrorDetail {
  code?: string;
  message?: string;
  grounding_issues?: Array<{ type: string; text: string }>;
  validation_issues?: string[];
  structure_issues?: string[];
}

export interface ChatEntry {
  id: string;
  message: MessageResponse;
  sources?: SourceResponse[];
  pending?: boolean;
  error?: string;
}

export type LoadingState =
  | "creating-session"
  | "loading-sessions"
  | "loading-messages"
  | "sending-message"
  | "creating-artifact-markdown"
  | "creating-artifact-html"
  | "creating-ship30"
  | null;

export const ARTIFACT_LOADING_STATES: LoadingState[] = [
  "creating-artifact-markdown",
  "creating-artifact-html",
  "creating-ship30",
];

export function isArtifactLoading(state: LoadingState): boolean {
  return ARTIFACT_LOADING_STATES.includes(state);
}

export function sessionDisplayTitle(session: SessionResponse | null): string {
  if (!session) return "Chat";
  if (session.title?.trim()) return session.title.trim();
  return "New conversation";
}
