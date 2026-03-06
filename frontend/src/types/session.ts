export interface SessionSummary {
  id: string;
  enquiry: string;
  status: string;
  max_rounds: number | null;
  current_round: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  total_duration_ms: number;
  created_at: string;
  completed_at: string | null;
  model_ids: string[];
}

export interface LLMCallEvent {
  id: string;
  model_slug: string;
  provider_slug: string;
  model_name: string;
  round_number: number;
  role: "responder" | "critic" | "summarizer";
  response: string;
  error: string | null;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
}

export interface TerminalEvent {
  status: string;
  current_round: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  total_duration_ms: number;
}

export type SessionStatus =
  | "pending"
  | "responding"
  | "critiquing"
  | "consensus_reached"
  | "max_rounds_reached"
  | "failed";

// Color assignments for models in chat UI
export const MODEL_COLORS = [
  "blue",
  "green",
  "orange",
  "grape",
  "cyan",
  "pink",
  "teal",
  "indigo",
] as const;
