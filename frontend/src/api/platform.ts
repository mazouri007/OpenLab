import { apiClient } from "./client";
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

export async function sendChatMessage(sessionId: string, content: string) {
  const response = await apiClient.post<ApiResponse<ChatAnswer>>(
    `/chat/sessions/${sessionId}/messages`,
    { content },
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function listDocuments(projectId: string) {
  const response = await apiClient.get<ApiResponse<KnowledgeDocument[]>>(
    `/projects/${projectId}/kb/documents`,
  );
  return response.data.data;
}

export async function createDocument(projectId: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<ApiResponse<KnowledgeDocument>>(
    `/projects/${projectId}/kb/documents`,
    payload,
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
