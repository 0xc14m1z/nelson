import { useCallback, useEffect, useRef, useState } from "react";
import { SSE } from "sse.js";
import { getAccessToken } from "@/lib/api";
import type {
  ModelCatchupEvent,
  ModelDoneEvent,
  ModelErrorEvent,
  ModelStartEvent,
  PhaseChangeEvent,
  RoundSummaryEvent,
  SessionStatus,
  TerminalEvent,
  TokenDeltaEvent,
} from "@/types/session";

export interface ModelStreamState {
  llm_model_id: string;
  round_number: number;
  role: "responder" | "critic" | "summarizer";
  text: string;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  structured: Record<string, unknown>;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
}

export interface PhaseInfo {
  round_number: number;
  phase: string;
  models: Array<{
    llm_model_id: string;
    model_name: string;
    confidence?: number;
    key_points?: string[];
    has_disagreements?: boolean;
    disagreements?: string[];
  }>;
  roundSummary: RoundSummaryEvent | null;
  collapsed: boolean;
}

interface UseConsensusStreamOptions {
  sessionId: string;
  enabled?: boolean;
}

interface ConsensusStreamState {
  models: Map<string, ModelStreamState>;
  phases: PhaseInfo[];
  status: SessionStatus;
  terminalEvent: TerminalEvent | null;
  isConnected: boolean;
  error: string | null;
}

function modelKey(llm_model_id: string, round_number: number): string {
  return `${llm_model_id}-${round_number}`;
}

export function useConsensusStream({ sessionId, enabled = true }: UseConsensusStreamOptions) {
  const [state, setState] = useState<ConsensusStreamState>({
    models: new Map(),
    phases: [],
    status: "pending",
    terminalEvent: null,
    isConnected: false,
    error: null,
  });
  const sourceRef = useRef<SSE | null>(null);

  const connect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const token = getAccessToken();
    const source = new SSE(`/api/sessions/${sessionId}/stream`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      start: false,
    });

    source.addEventListener("model_start", (e: MessageEvent) => {
      try {
        const data: ModelStartEvent = JSON.parse(e.data);
        const key = modelKey(data.llm_model_id, data.round_number);
        setState((prev) => {
          const next = new Map(prev.models);
          next.set(key, {
            llm_model_id: data.llm_model_id,
            round_number: data.round_number,
            role: data.role,
            text: "",
            isStreaming: true,
            isDone: false,
            error: null,
            structured: {},
            input_tokens: 0,
            output_tokens: 0,
            cost: 0,
            duration_ms: 0,
          });
          return {
            ...prev,
            models: next,
            status: data.role === "responder" ? "responding" : "critiquing",
          };
        });
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("token_delta", (e: MessageEvent) => {
      try {
        const data: TokenDeltaEvent = JSON.parse(e.data);
        const key = modelKey(data.llm_model_id, data.round_number);
        setState((prev) => {
          const existing = prev.models.get(key);
          if (!existing) return prev;
          const next = new Map(prev.models);
          next.set(key, {
            ...existing,
            text: existing.text + data.delta,
          });
          return { ...prev, models: next };
        });
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("model_done", (e: MessageEvent) => {
      try {
        const data: ModelDoneEvent = JSON.parse(e.data);
        const key = modelKey(data.llm_model_id, data.round_number);
        setState((prev) => {
          const existing = prev.models.get(key);
          const next = new Map(prev.models);
          next.set(key, {
            llm_model_id: data.llm_model_id,
            round_number: data.round_number,
            role: data.role,
            text: data.response ?? existing?.text ?? "",
            isStreaming: false,
            isDone: true,
            error: data.error ?? null,
            structured: data.structured,
            input_tokens: data.input_tokens,
            output_tokens: data.output_tokens,
            cost: data.cost,
            duration_ms: data.duration_ms,
          });
          return { ...prev, models: next };
        });
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("model_error", (e: MessageEvent) => {
      try {
        const data: ModelErrorEvent = JSON.parse(e.data);
        const key = modelKey(data.llm_model_id, data.round_number);
        setState((prev) => {
          const existing = prev.models.get(key);
          if (!existing) return prev;
          const next = new Map(prev.models);
          next.set(key, {
            ...existing,
            isStreaming: false,
            isDone: true,
            error: data.error,
          });
          return { ...prev, models: next };
        });
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("model_catchup", (e: MessageEvent) => {
      try {
        const data: ModelCatchupEvent = JSON.parse(e.data);
        const key = modelKey(data.llm_model_id, data.round_number);
        setState((prev) => {
          const next = new Map(prev.models);
          const existing = next.get(key);
          if (existing) {
            next.set(key, { ...existing, text: data.text_so_far });
          } else {
            // Catchup arrived before model_start — create entry implicitly
            next.set(key, {
              llm_model_id: data.llm_model_id,
              round_number: data.round_number,
              role: data.role,
              text: data.text_so_far,
              isStreaming: true,
              isDone: false,
              error: null,
              structured: {},
              input_tokens: 0,
              output_tokens: 0,
              cost: 0,
              duration_ms: 0,
            });
          }
          return { ...prev, models: next };
        });
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("phase_change", (e: MessageEvent) => {
      try {
        const data: PhaseChangeEvent = JSON.parse(e.data);
        setState((prev) => ({
          ...prev,
          phases: [
            ...prev.phases,
            {
              round_number: data.round_number,
              phase: data.phase,
              models: data.models,
              roundSummary: null,
              collapsed: true,
            },
          ],
        }));
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("round_summary", (e: MessageEvent) => {
      try {
        const data: RoundSummaryEvent = JSON.parse(e.data);
        setState((prev) => ({
          ...prev,
          phases: prev.phases.map((p) =>
            p.round_number === data.round_number ? { ...p, roundSummary: data } : p,
          ),
        }));
      } catch {
        // ignore parse errors
      }
    });

    const handleTerminal = (eventType: SessionStatus) => (e: MessageEvent) => {
      try {
        const data: TerminalEvent = JSON.parse(e.data);
        setState((prev) => ({
          ...prev,
          status: eventType,
          terminalEvent: data,
          isConnected: false,
        }));
        source.close();
      } catch {
        // ignore parse errors
      }
    };

    source.addEventListener("consensus_reached", handleTerminal("consensus_reached"));
    source.addEventListener("max_rounds_reached", handleTerminal("max_rounds_reached"));
    source.addEventListener("failed", handleTerminal("failed"));

    source.addEventListener("open", () => {
      setState((prev) => ({ ...prev, isConnected: true, error: null }));
    });

    source.addEventListener("error", () => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        error: "Connection lost",
      }));
    });

    sourceRef.current = source;
    source.stream();
  }, [sessionId]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return () => {
      sourceRef.current?.close();
    };
  }, [enabled, connect]);

  const togglePhase = useCallback((index: number) => {
    setState((prev) => ({
      ...prev,
      phases: prev.phases.map((p, i) => (i === index ? { ...p, collapsed: !p.collapsed } : p)),
    }));
  }, []);

  return { ...state, togglePhase };
}
