import { authHeaders } from "./session";
import type {
  Arm, Comparison, GraphNode, Mode, Provider, ResearchConfig, SessionUser,
  StudentOptions, Summary, Template, TelemetryEvent, TimelinePoint, Turn,
  TurnResult, Workspace,
} from "./types";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  signIn: (display_name: string, role: "student" | "researcher") =>
    json<SessionUser>("/api/session", {
      method: "POST",
      body: JSON.stringify({ display_name, role }),
    }),

  participants: () => json<SessionUser[]>("/api/participants"),

  options: () => json<StudentOptions>("/api/options"),

  arms: () => json<Arm[]>("/api/research/experiments"),

  createArm: (body: Partial<Arm>) =>
    json<Arm>("/api/research/experiments", { method: "POST", body: JSON.stringify(body) }),

  updateArm: (armId: string, body: Partial<Arm>) =>
    json<Arm>(`/api/research/experiments/${armId}`, {
      method: "PATCH", body: JSON.stringify(body),
    }),

  deleteArm: (armId: string) =>
    json<{ ok: boolean }>(`/api/research/experiments/${armId}`, { method: "DELETE" }),

  assign: (body: { user_id?: string; arm_id?: string; randomise?: boolean; seed?: number }) =>
    json<{ ok: boolean; assigned: number }>("/api/research/experiments/assign", {
      method: "POST", body: JSON.stringify(body),
    }),

  compare: () => json<Comparison>("/api/research/experiments/compare"),

  templates: () => json<{ templates: Template[] }>("/api/templates").then((r) => r.templates),

  timeline: (workspaceId = "") =>
    json<{ points: TimelinePoint[] }>(
      `/api/research/timeline${workspaceId ? `?workspace_id=${workspaceId}` : ""}`,
    ).then((r) => r.points),

  modes: () => json<{ modes: Mode[] }>("/api/workspaces/modes").then((r) => r.modes),

  listWorkspaces: () => json<Workspace[]>("/api/workspaces"),

  createWorkspace: (body: { title: string; initial_prompt: string; mode: string }) =>
    json<Workspace>("/api/workspaces", { method: "POST", body: JSON.stringify(body) }),

  getWorkspace: (id: string) => json<Workspace>(`/api/workspaces/${id}`),

  updateWorkspace: (id: string, body: Partial<Workspace>) =>
    json<Workspace>(`/api/workspaces/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  deleteWorkspace: (id: string) =>
    json<{ ok: boolean }>(`/api/workspaces/${id}`, { method: "DELETE" }),

  turns: (id: string) => json<Turn[]>(`/api/workspaces/${id}/turns`),

  graph: () => json<{ nodes: GraphNode[] }>("/api/graph").then((r) => r.nodes),

  providers: () =>
    json<{ providers: Provider[]; default: string }>("/api/research/providers"),

  config: () => json<ResearchConfig>("/api/research/config"),

  updateConfig: (body: Partial<ResearchConfig>) =>
    json<{ ok: boolean; changed: string[] }>("/api/research/config", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  summary: () => json<Summary>("/api/research/summary"),

  events: (limit = 60, workspaceId = "") =>
    json<TelemetryEvent[]>(
      `/api/research/events?limit=${limit}${workspaceId ? `&workspace_id=${workspaceId}` : ""}`,
    ),

  /** Fire-and-forget telemetry. Never blocks or throws into the writing path. */
  logEvent: (body: {
    workspace_id?: string;
    event_type: string;
    delta_change?: number;
    duration_ms?: number;
    payload?: Record<string, unknown>;
  }) => {
    void fetch("/api/research/events", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => {});
  },
};

/**
 * Run one co-creative turn, surfacing each graph node as it executes.
 *
 * The per-node callback is the point: the interface shows the Helsinki filter
 * firing before the reply lands, so the student sees *why* they got a question.
 */
export async function streamTurn(
  workspaceId: string,
  body: {
    message: string;
    draft: string;
    selection?: string;
    provider?: string;
    model?: string;
    intensity?: string;
  },
  onNode: (id: string, status: string, extra: Record<string, unknown>) => void,
): Promise<TurnResult> {
  const res = await fetch(`/api/workspaces/${workspaceId}/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`Turn failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: TurnResult | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      if (!block.trim()) continue;
      const lines = block.split("\n");
      const evLine = lines.find((l) => l.startsWith("event:"));
      const dataLine = lines.find((l) => l.startsWith("data:"));
      if (!evLine || !dataLine) continue;

      const event = evLine.slice(6).trim();
      const data = JSON.parse(dataLine.slice(5).trim());

      if (event === "node") {
        const { id, status, ...extra } = data;
        onNode(id, status, extra);
      } else if (event === "done") {
        result = data as TurnResult;
      }
    }
  }

  if (!result) throw new Error("Stream ended without a result");
  return result;
}
