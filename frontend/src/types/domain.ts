export type Project = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  primary_language: string;
};

export type ReviewTask = {
  id: string;
  title: string;
  language: string;
  source_type: string;
  status: string;
  progress_stage: string;
  error_message?: string | null;
};

export type ReviewFinding = {
  severity: "critical" | "high" | "medium" | "low" | "info";
  category: string;
  title: string;
  evidence: string;
  impact: string;
  suggestion: string;
  example_fix?: string | null;
};

export type ReviewResult = {
  summary: string;
  overall_risk: string;
  findings: ReviewFinding[];
  suggestions: { label?: string }[];
  positive_notes: string[];
  uncertain_points: string[];
};

export type TestTask = {
  id: string;
  language: string;
  framework: string;
  target_name: string;
  status: string;
  progress_stage: string;
  error_message?: string | null;
};

export type TestResult = {
  test_code: string;
  scenarios: { name: string; case_type: string; description: string }[];
  self_check_report: Record<string, unknown>;
};

export type ChatSession = {
  id: string;
  title: string;
  status: string;
};

export type ChatMessage = {
  id: string;
  role: string;
  content: string;
  citations_json: Record<string, unknown>[];
};

export type ChatAnswer = {
  answer: string;
  citations: {
    chunk_id: string;
    snippet: string;
    source_type: string;
    source_title?: string | null;
  }[];
  used_memory: string[];
  used_documents: string[];
  rewritten_queries: string[];
  reasoning_summary: string;
  confidence: number;
};

export type KnowledgeDocument = {
  id: string;
  title: string;
  source_type: string;
  source_name?: string | null;
  parse_status: string;
  chunk_count: number;
  error_message?: string | null;
  created_at?: string | null;
};

export type GithubRepository = {
  id: string;
  repo_full_name: string;
  default_branch: string;
  status: string;
  last_synced_at?: string | null;
  open_pr_count: number;
};

export type ModelProvider = {
  id: string;
  name: string;
  provider_type: string;
  base_url?: string | null;
  default_chat_model: string;
  default_embedding_model: string;
  is_default: boolean;
};

export type TaskStatus = {
  id: string;
  task_type: string;
  status: string;
  progress_stage: string;
  error_message?: string | null;
  updated_at?: string | null;
};
