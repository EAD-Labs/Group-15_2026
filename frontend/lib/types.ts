export type SessionUser = {
  user_id: string;
  display_name: string;
  role: "student" | "researcher";
  participant_code: string;
  arm_id: string;
};

export type Template = {
  id: string;
  label: string;
  prompt: string;
  cognitive: CognitiveActivity;
  origin: string;
  inverted: boolean;
};

export type CognitiveActivity = "planning" | "translation" | "reviewing" | "other" | "";

// What the writer declares (Flower & Hayes' Monitor). Spelled "translating" to
// match the client and the UI copy; the detected axis stores "translation".
export type DeclaredActivity = "planning" | "translating" | "reviewing" | "";

export const DECLARED_ACTIVITIES: Exclude<DeclaredActivity, "">[] = [
  "planning", "translating", "reviewing",
];

export type TimelinePoint = {
  index: number;
  workspace_id: string;
  intent: Intent;
  cognitive: CognitiveActivity;
  declared: DeclaredActivity;
  intercepted: boolean;
  message: string;
  timestamp: string;
};

export type Intensity = "light" | "balanced" | "deep";

export type IntensityOption = { id: Intensity; label: string; blurb: string };

export type StudentOptions = {
  condition: { arm_id: string; name: string } | null;
  guardrail_active: boolean;
  allow_intensity: boolean;
  allow_model: boolean;
  intensities: IntensityOption[];
  providers: Provider[];
};

export type Archetype = "ghost" | "partner" | "tutor" | "custom";

export type AIRole = {
  role_id: string;
  name: string;
  archetype: Archetype;
  behaviour: string;
  base_prompt: string;
  planning_prompt: string;
  translating_prompt: string;
  reviewing_prompt: string;
  may_produce_prose: boolean;
  enforcement_level: number;
  version: number;
  parent_role_id: string;
  created_at: string;
};

export type Arm = {
  arm_id: string;
  name: string;
  description: string;
  provider: string;
  model_name: string;
  temperature: number;
  guardrail_strictness: number;
  role_id: string;
  role_name?: string | null;
  scaffold_intensity: Intensity;
  system_prompt: string;
  allow_student_intensity: boolean;
  allow_student_model: boolean;
  allowed_providers: string[];
  is_control: boolean;
  is_default: boolean;
  active: boolean;
  participants: number;
};

export type ArmOutcome = {
  arm_id: string;
  name: string;
  is_control: boolean;
  config: {
    provider: string;
    model_name: string;
    temperature: number;
    guardrail_strictness: number;
    scaffold_intensity: string;
  };
  participants: number;
  workspaces: number;
  exchanges: number;
  mean_agency: number | null;
  mean_ai_retention: number | null;
  retention_by_activity: Record<string, number | null>;
  mean_words: number | null;
  words_per_exchange: number | null;
  intercept_rate: number | null;
  median_latency_ms: number | null;
  intent_distribution: Record<string, number>;
  cognitive_distribution: Record<string, number>;
  intensity_used: Record<string, number>;
};

export type Comparison = {
  arms: ArmOutcome[];
  unassigned_participants: number;
  measures: Record<string, string>;
  intensities: IntensityOption[];
};

export type Mode = {
  id: string;
  label: string;
  blurb: string;
  starters: string[];
};

export type Workspace = {
  workspace_id: string;
  title: string;
  initial_prompt: string;
  current_content: string;
  goals: string;
  mode: string;
  status: string;
  created_at: string;
  updated_at: string;
  word_count: number;
  agency_ratio: number;
  ai_retention: number;
  turn_count: number;
  owner: string;
  scaffold_intensity: Intensity;
};

export type Intent = "executive" | "instrumental" | "brainstorm" | "reflection" | "";

export type Turn = {
  turn_id: string;
  speaker: "user" | "ai";
  message_text: string;
  intent_type: Intent;
  cognitive_activity: CognitiveActivity;
  declared_activity?: DeclaredActivity;
  intercepted: boolean;
  node_path: string[];
  suggestions: string[];
  provider: string;
  model_name: string;
  latency_ms: number;
  timestamp: string;
};

export type TurnResult = {
  turn_id: string;
  response_text: string;
  probes: string[];
  intent: Intent;
  cognitive: CognitiveActivity;
  declared_activity?: DeclaredActivity;
  effective_activity?: string;
  intensity: Intensity;
  intercepted: boolean;
  node_path: string[];
  enforcement: string[];
  provider: string;
  model_name: string;
  latency_ms: number;
  error?: string;
};

export type GraphNode = {
  id: string;
  label: string;
  desc: string;
  next: string[];
};

export type Provider = {
  id: string;
  label: string;
  model: string;
  hint: string;
  healthy: boolean;
  status: string;
};

export type ResearchConfig = {
  config_id: string;
  label: string;
  provider: string;
  model_name: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  guardrail_strictness: number;
  default_system_prompt: string;
};

export type TelemetryEvent = {
  event_id: string;
  workspace_id: string;
  event_type: string;
  delta_change: number;
  duration_ms: number;
  payload: Record<string, unknown>;
  timestamp: string;
};

export type Summary = {
  workspaces: number;
  total_words: number;
  exchanges: number;
  intercepts: number;
  intercept_rate: number;
  mean_agency: number;
  median_latency_ms: number;
  intent_distribution: Record<string, number>;
  cognitive_distribution: Record<string, number>;
  declared_distribution: Record<string, number>;
  retention_by_activity: Record<string, number | null>;
  mean_ai_retention: number;
  enforcement_actions: Record<string, number>;
  event_count: number;
  per_workspace: {
    workspace_id: string;
    title: string;
    mode: string;
    words: number;
    agency_ratio: number;
    ai_retention: number;
    borrowed_ngrams: number;
    turns: number;
    updated_at: string;
  }[];
};
