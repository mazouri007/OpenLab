import { API_BASE_URL, apiClient } from "./client";
import type {
  ChatAnswer,
  ChatMessage,
  ChatSession,
  GithubRepository,
  KnowledgeDocument,
  ModelProvider,
  Project,
  ReviewResult,
  ReviewTask,
  TaskStatus,
  TestResult,
  TestTask,
} from "../types/domain";
import type { ApiResponse } from "../types/api";

export type ChatMessagePayload = {
  content: string;
  context_type?: "general" | "github_commit";
  action?: "auto" | "answer" | "review" | "test" | "review_and_test";
  repository_id?: string;
  commit_sha?: string;
  pr_number?: number;
  intent?: "auto" | "explain" | "compliance" | "review";
  persist_review?: boolean;
  persist_results?: boolean;
  language?: string;
  framework?: string;
};

export type ChatStreamStatus = {
  stage: "recall" | "retrieve" | "generate" | "persist";
  message: string;
};

export type ChatStreamHandlers = {
  onStatus?: (status: ChatStreamStatus) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: { answer: ChatAnswer; assistant_message_id: string }) => void;
  onError?: (detail: string) => void;
};

export async function listProjects() {
  const response = await apiClient.get<ApiResponse<Project[]>>("/projects");
  return response.data.data;
}

export async function listReviewTasks(projectId: string) {
  const response = await apiClient.get<ApiResponse<ReviewTask[]>>(`/projects/${projectId}/reviews`);
  return response.data.data;
}

export async function createReviewTask(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<ApiResponse<ReviewTask>>(`/projects/${projectId}/reviews`, payload);
  return response.data.data;
}

export async function getReviewResult(taskId: string) {
  const response = await apiClient.get<ApiResponse<ReviewResult>>(`/reviews/${taskId}/result`);
  return response.data.data;
}

export async function listTestTasks(projectId: string) {
  const response = await apiClient.get<ApiResponse<TestTask[]>>(
    `/projects/${projectId}/test-generations`,
  );
  return response.data.data;
}

export async function createTestTask(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<ApiResponse<TestTask>>(
    `/projects/${projectId}/test-generations`,
    payload,
  );
  return response.data.data;
}

export async function getTestResult(taskId: string) {
  const response = await apiClient.get<ApiResponse<TestResult>>(`/test-generations/${taskId}/result`);
  return response.data.data;
}

export async function listChatSessions(projectId: string) {
  const response = await apiClient.get<ApiResponse<ChatSession[]>>(
    `/projects/${projectId}/chat/sessions`,
  );
  return response.data.data;
}

export async function createChatSession(projectId: string, title: string) {
  const response = await apiClient.post<ApiResponse<ChatSession>>(
    `/projects/${projectId}/chat/sessions`,
    { title, user_id: "demo-user" },
  );
  return response.data.data;
}

export async function listChatMessages(sessionId: string) {
  const response = await apiClient.get<ApiResponse<ChatMessage[]>>(`/chat/sessions/${sessionId}/messages`);
  return response.data.data;
}

export async function sendChatMessage(sessionId: string, payload: string | ChatMessagePayload) {
  const body = typeof payload === "string" ? { content: payload } : payload;
  const response = await apiClient.post<ApiResponse<ChatAnswer>>(
    `/chat/sessions/${sessionId}/messages`,
    body,
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function streamChatMessage(
  sessionId: string,
  payload: string | ChatMessagePayload,
  handlers: ChatStreamHandlers,
) {
  const body = typeof payload === "string" ? { content: payload } : payload;
  const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const detail = await readFetchError(response);
    throw new Error(detail || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      handleSseBlock(block, handlers);
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) {
    handleSseBlock(buffer, handlers);
  }
}

export async function listDocuments(projectId: string) {
  const response = await apiClient.get<ApiResponse<KnowledgeDocument[]>>(
    `/projects/${projectId}/kb/documents`,
  );
  return response.data.data;
}

async function readFetchError(response: Response) {
  try {
    const payload = await response.json();
    return payload.detail ?? payload.message ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

function handleSseBlock(block: string, handlers: ChatStreamHandlers) {
  const lines = block.split("\n");
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (!dataLines.length) {
    return;
  }
  const payload = JSON.parse(dataLines.join("\n"));
  if (eventName === "status") {
    handlers.onStatus?.(payload as ChatStreamStatus);
  } else if (eventName === "delta") {
    handlers.onDelta?.(String(payload.content ?? ""));
  } else if (eventName === "done") {
    handlers.onDone?.(payload as { answer: ChatAnswer; assistant_message_id: string });
  } else if (eventName === "error") {
    handlers.onError?.(String(payload.detail ?? "聊天流式调用失败"));
  }
}

export async function createDocument(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<ApiResponse<KnowledgeDocument>>(
    `/projects/${projectId}/kb/documents`,
    payload,
  );
  return response.data.data;
}

export async function uploadDocument(projectId: string, payload: { file: File; title?: string }) {
  const formData = new FormData();
  formData.append("file", payload.file);
  if (payload.title) {
    formData.append("title", payload.title);
  }
  const response = await apiClient.post<ApiResponse<KnowledgeDocument>>(
    `/projects/${projectId}/kb/documents/upload`,
    formData,
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function listRepositories(projectId: string) {
  const response = await apiClient.get<ApiResponse<GithubRepository[]>>(
    `/projects/${projectId}/github/repositories`,
  );
  return response.data.data;
}

export async function syncRepositories(projectId: string) {
  const response = await apiClient.post<ApiResponse<GithubRepository[]>>(
    `/projects/${projectId}/github/repositories/sync`,
  );
  return response.data.data;
}

export async function createGithubIntegration(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<ApiResponse<{ id: string; status: string }>>(
    `/projects/${projectId}/github/integrations`,
    payload,
  );
  return response.data.data;
}

export async function listProviders(projectId: string) {
  const response = await apiClient.get<ApiResponse<ModelProvider[]>>(
    `/projects/${projectId}/models/providers`,
  );
  return response.data.data;
}

export async function createProvider(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<ApiResponse<ModelProvider>>(
    `/projects/${projectId}/models/providers`,
    payload,
  );
  return response.data.data;
}

export async function updateProvider(
  projectId: string,
  providerId: string,
  payload: Record<string, unknown>,
) {
  const response = await apiClient.patch<ApiResponse<ModelProvider>>(
    `/projects/${projectId}/models/providers/${providerId}`,
    payload,
  );
  return response.data.data;
}

export async function updateProviderSecrets(
  projectId: string,
  providerId: string,
  payload: Record<string, unknown>,
) {
  const response = await apiClient.patch<ApiResponse<ModelProvider>>(
    `/projects/${projectId}/models/providers/${providerId}/secrets`,
    payload,
  );
  return response.data.data;
}

export async function testProvider(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<
    ApiResponse<{ ok: boolean; model: string; message: string }>
  >(`/projects/${projectId}/models/providers/test`, payload);
  return response.data.data;
}

export async function getTaskStatus(taskId: string) {
  const response = await apiClient.get<ApiResponse<TaskStatus>>(`/tasks/${taskId}`);
  return response.data.data;
}
