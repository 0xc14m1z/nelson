import { useCallback, useEffect, useRef, useState } from "react";
import { SSE } from "sse.js";
import { getAccessToken } from "@/lib/api";
import type { LLMCallEvent, SessionStatus, TerminalEvent } from "@/types/session";

interface UseConsensusStreamOptions {
  sessionId: string;
  enabled?: boolean;
}

interface ConsensusStreamState {
  events: LLMCallEvent[];
  status: SessionStatus;
  terminalEvent: TerminalEvent | null;
  isConnected: boolean;
  error: string | null;
}

export function useConsensusStream({ sessionId, enabled = true }: UseConsensusStreamOptions) {
  const [state, setState] = useState<ConsensusStreamState>({
    events: [],
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

    const handleEvent = (eventType: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);

        if (["consensus_reached", "max_rounds_reached", "failed"].includes(eventType)) {
          setState((prev) => ({
            ...prev,
            status: eventType as SessionStatus,
            terminalEvent: data,
            isConnected: false,
          }));
          source.close();
          return;
        }

        setState((prev) => ({
          ...prev,
          events: [...prev.events, data as LLMCallEvent],
          status:
            eventType === "model_dropped"
              ? prev.status
              : data.role === "responder"
                ? "responding"
                : "critiquing",
        }));
      } catch {
        // ignore parse errors
      }
    };

    source.addEventListener("responder", handleEvent("responder"));
    source.addEventListener("critic", handleEvent("critic"));
    source.addEventListener("summarizer", handleEvent("summarizer"));
    source.addEventListener("model_dropped", handleEvent("model_dropped"));
    source.addEventListener("consensus_reached", handleEvent("consensus_reached"));
    source.addEventListener("max_rounds_reached", handleEvent("max_rounds_reached"));
    source.addEventListener("failed", handleEvent("failed"));

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

  return state;
}
