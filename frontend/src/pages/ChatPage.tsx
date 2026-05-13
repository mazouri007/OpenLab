import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Select,
  Skeleton,
  Space,
  Typography,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  createChatSession,
  listRepositories,
  listChatMessages,
  listChatSessions,
  streamChatMessage,
  type ChatStreamStatus,
  type ChatMessagePayload,
} from "../api/platform";
import { CitationList } from "../components/CitationList";
import { MessageContent } from "../components/MessageContent";
import { PageHeader } from "../components/PageHeader";
import { useCurrentProject } from "../hooks/useCurrentProject";
import type { ChatAnswer, ChatMessage, ChatSession } from "../types/domain";

type LocalExchange = {
  id: string;
  sessionId: string;
  question: string;
  answer: ChatAnswer;
  status?: string;
  isStreaming: boolean;
};

type DisplayMessage = Pick<ChatMessage, "id" | "role" | "content" | "citations_json">;

type CreateSessionForm = {
  title: string;
};

type CommitIntent = "auto" | "explain" | "compliance" | "review";
type ChatAction = "auto" | "answer" | "review" | "test" | "review_and_test";

export default function ChatPage() {
  const { projectId } = useCurrentProject();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<CreateSessionForm>();
  const [input, setInput] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [lastExchange, setLastExchange] = useState<LocalExchange | null>(null);
  const [commitEnabled, setCommitEnabled] = useState(false);
  const [commitRepositoryId, setCommitRepositoryId] = useState<string>();
  const [commitSha, setCommitSha] = useState("");
  const [prNumber, setPrNumber] = useState<number | null>(null);
  const [commitIntent, setCommitIntent] = useState<CommitIntent>("auto");
  const [chatAction, setChatAction] = useState<ChatAction>("auto");
  const [language, setLanguage] = useState<string>();
  const [framework, setFramework] = useState<string>();
  const [persistReview, setPersistReview] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);

  const sessionsQuery = useQuery({
    queryKey: ["chat-sessions", projectId],
    queryFn: () => listChatSessions(projectId),
    enabled: !!projectId,
  });

  useEffect(() => {
    if (!selectedSession && sessionsQuery.data?.[0]) {
      setSelectedSession(sessionsQuery.data[0]);
    }
  }, [selectedSession, sessionsQuery.data]);

  const messagesQuery = useQuery({
    queryKey: ["chat-messages", selectedSession?.id],
    queryFn: () => listChatMessages(selectedSession!.id),
    enabled: !!selectedSession?.id,
  });

  const reposQuery = useQuery({
    queryKey: ["repos", projectId],
    queryFn: () => listRepositories(projectId),
    enabled: !!projectId,
  });

  const repoOptions = useMemo(
    () =>
      (reposQuery.data ?? []).map((repo) => ({
        value: repo.id,
        label: repo.repo_full_name,
      })),
    [reposQuery.data],
  );

  const createSessionMutation = useMutation({
    mutationFn: (values: CreateSessionForm) => createChatSession(projectId, values.title.trim()),
    onSuccess: async (session) => {
      setSelectedSession(session);
      setLastExchange(null);
      setCreateOpen(false);
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", projectId] });
    },
    onError: (error: Error) => {
      message.error(`新建会话失败：${error.message}`);
    },
  });

  const displayedMessages = useMemo<DisplayMessage[]>(() => {
    const serverMessages = messagesQuery.data ?? [];
    const merged: DisplayMessage[] = [...serverMessages];
    if (!lastExchange || lastExchange.sessionId !== selectedSession?.id) {
      return merged;
    }

    const hasQuestion = serverMessages.some(
      (item) => item.role === "user" && item.content === lastExchange.question,
    );
    const hasAnswer = serverMessages.some(
      (item) => item.role === "assistant" && item.content === lastExchange.answer.answer,
    );

    if (!hasQuestion) {
      merged.push({
        id: `local-user-${lastExchange.id}`,
        role: "user",
        content: lastExchange.question,
        citations_json: [],
      });
    }
    if (!hasAnswer) {
      merged.push({
        id: `local-assistant-${lastExchange.id}`,
        role: "assistant",
        content: lastExchange.answer.answer || lastExchange.status || "正在生成回答...",
        citations_json: lastExchange.answer.citations,
      });
    }
    return merged;
  }, [lastExchange, messagesQuery.data, selectedSession?.id]);

  const lastAnswer =
    lastExchange && lastExchange.sessionId === selectedSession?.id ? lastExchange.answer : null;

  const submitQuestion = async () => {
    const content = input.trim();
    if (!selectedSession || !content || isStreaming) {
      return;
    }
    if (commitEnabled && (!commitRepositoryId || (!commitSha.trim() && !prNumber))) {
      message.warning("请选择仓库，并填写 commit SHA 或 PR 编号。");
      return;
    }
    const payload: ChatMessagePayload = commitEnabled
      ? {
          content,
          context_type: commitSha.trim() ? "github_commit" : "general",
          action: chatAction,
          repository_id: commitRepositoryId,
          commit_sha: commitSha.trim() || undefined,
          pr_number: prNumber || undefined,
          intent: commitIntent,
          persist_review: persistReview,
          persist_results: persistReview,
          language,
          framework: framework?.trim() || undefined,
        }
      : { content, action: chatAction };
    const sessionId = selectedSession.id;
    const exchangeId = `${sessionId}-${Date.now()}`;
    const emptyAnswer: ChatAnswer = {
      answer: "",
      citations: [],
      used_memory: [],
      used_documents: [],
      rewritten_queries: [],
      reasoning_summary: "",
      confidence: 0,
      metadata: {},
    };
    setLastExchange({
      id: exchangeId,
      sessionId,
      question: content,
      answer: emptyAnswer,
      status: "正在准备回答...",
      isStreaming: true,
    });
    setInput("");
    setIsStreaming(true);
    const updateExchange = (updater: (current: LocalExchange) => LocalExchange) => {
      setLastExchange((current) => {
        if (!current || current.id !== exchangeId) {
          return current;
        }
        return updater(current);
      });
    };
    try {
      await streamChatMessage(sessionId, payload, {
        onStatus: (status: ChatStreamStatus) => {
          updateExchange((current) => ({ ...current, status: status.message }));
        },
        onDelta: (delta) => {
          updateExchange((current) => ({
            ...current,
            answer: { ...current.answer, answer: current.answer.answer + delta },
          }));
        },
        onDone: ({ answer }) => {
          updateExchange((current) => ({
            ...current,
            answer,
            status: undefined,
            isStreaming: false,
          }));
        },
        onError: (detail) => {
          updateExchange((current) => ({
            ...current,
            status: detail,
            isStreaming: false,
          }));
          message.error(`发送失败：${detail}`);
        },
      });
      await queryClient.invalidateQueries({ queryKey: ["chat-messages", sessionId] });
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", projectId] });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "未知错误";
      updateExchange((current) => ({
        ...current,
        status: detail,
        isStreaming: false,
      }));
      message.error(`发送失败：${detail}`);
    } finally {
      setIsStreaming(false);
    }
  };

  const submitCreateSession = async () => {
    const values = await form.validateFields();
    createSessionMutation.mutate(values);
  };

  const canSubmit =
    !!selectedSession &&
    !!input.trim() &&
    (!commitEnabled || (!!commitRepositoryId && (!!commitSha.trim() || !!prNumber)));

  return (
    <div className="page-grid">
      <PageHeader
        title="知识问答"
        description="结合项目知识库、短期摘要与长期记忆进行研发问答，并返回引用证据。"
        extra={
          <Button
            type="primary"
            onClick={() => {
              form.setFieldsValue({ title: `研发问答 ${new Date().toLocaleString()}` });
              setCreateOpen(true);
            }}
            disabled={!projectId}
          >
            新建会话
          </Button>
        }
      />

      <div className="chat-layout">
        <Card className="content-card" title="会话列表">
          <List
            loading={sessionsQuery.isLoading}
            dataSource={sessionsQuery.data ?? []}
            locale={{ emptyText: "暂无会话，请先新建会话" }}
            renderItem={(item) => (
              <List.Item
                onClick={() => {
                  setSelectedSession(item);
                  setLastExchange(null);
                }}
                style={{
                  cursor: "pointer",
                  background: selectedSession?.id === item.id ? "#eff6ff" : "transparent",
                  borderRadius: 10,
                  paddingInline: 12,
                }}
              >
                <div>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <div>
                    <Typography.Text type="secondary">{item.status}</Typography.Text>
                  </div>
                </div>
              </List.Item>
            )}
          />
        </Card>

        <Card className="content-card" title={selectedSession?.title ?? "会话"}>
          {!selectedSession ? (
            <Alert showIcon type="info" message="请先新建或选择一个会话。" />
          ) : null}
          {messagesQuery.isLoading ? <Skeleton active /> : null}
          <div className="message-list">
            {displayedMessages.map((chatMessage) => (
              <div key={chatMessage.id} className={`message-item ${chatMessage.role}`}>
                <Typography.Text strong>
                  {chatMessage.role === "user" ? "你" : "AI 助手"}
                </Typography.Text>
                <MessageContent content={chatMessage.content} />
              </div>
            ))}
          </div>
          <Input.TextArea
            value={input}
            rows={5}
            placeholder="询问实验室规范、历史 review、项目约定或测试策略"
            style={{ marginTop: 16 }}
            onChange={(event) => setInput(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault();
                submitQuestion();
              }
            }}
          />
          <Space wrap size="middle" style={{ marginTop: 12 }}>
            <Select<ChatAction>
              style={{ width: 170 }}
              value={chatAction}
              onChange={setChatAction}
              options={[
                { value: "auto", label: "自动识别动作" },
                { value: "answer", label: "只回答" },
                { value: "review", label: "代码审查" },
                { value: "test", label: "生成测试" },
                { value: "review_and_test", label: "审查并测试" },
              ]}
            />
          </Space>
          <div className="commit-context-panel">
            <Checkbox
              checked={commitEnabled}
              onChange={(event) => setCommitEnabled(event.target.checked)}
            >
              精确指定 GitHub 上下文
            </Checkbox>
            {commitEnabled ? (
              <Space wrap size="middle" style={{ marginTop: 12 }}>
                <Select
                  showSearch
                  style={{ width: 260 }}
                  placeholder="选择仓库"
                  options={repoOptions}
                  loading={reposQuery.isLoading}
                  value={commitRepositoryId}
                  optionFilterProp="label"
                  onChange={setCommitRepositoryId}
                />
                <Input
                  style={{ width: 220 }}
                  placeholder="commit SHA"
                  value={commitSha}
                  onChange={(event) => setCommitSha(event.target.value)}
                />
                <InputNumber
                  style={{ width: 130 }}
                  min={1}
                  precision={0}
                  placeholder="PR 编号"
                  value={prNumber}
                  onChange={setPrNumber}
                />
                <Select<CommitIntent>
                  style={{ width: 150 }}
                  value={commitIntent}
                  onChange={setCommitIntent}
                  options={[
                    { value: "auto", label: "自动判断" },
                    { value: "explain", label: "功能说明" },
                    { value: "compliance", label: "规范判断" },
                    { value: "review", label: "代码审查" },
                  ]}
                />
                <Select
                  allowClear
                  style={{ width: 140 }}
                  placeholder="语言"
                  value={language}
                  onChange={setLanguage}
                  options={[
                    { value: "python", label: "Python" },
                    { value: "java", label: "Java" },
                  ]}
                />
                <Input
                  style={{ width: 160 }}
                  placeholder="测试框架"
                  value={framework}
                  onChange={(event) => setFramework(event.target.value)}
                />
                <Checkbox
                  checked={persistReview}
                  onChange={(event) => setPersistReview(event.target.checked)}
                >
                  保存任务结果
                </Checkbox>
              </Space>
            ) : null}
          </div>
          <Button
            type="primary"
            style={{ marginTop: 12 }}
            disabled={!canSubmit}
            loading={isStreaming}
            onClick={submitQuestion}
          >
            发送问题
          </Button>
        </Card>

        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Card className="content-card" title="引用来源">
            <CitationList citations={lastAnswer?.citations ?? []} />
          </Card>
          <Card className="content-card" title="摘要与记忆">
            <Typography.Paragraph>
              <strong>重写查询：</strong>
              {(lastAnswer?.rewritten_queries ?? []).join(" / ") || "暂无"}
            </Typography.Paragraph>
            <Typography.Paragraph>
              <strong>长期记忆：</strong>
              {(lastAnswer?.used_memory ?? []).join("；") || "暂无召回"}
            </Typography.Paragraph>
            <Typography.Paragraph>
              <strong>推理摘要：</strong>
              {lastAnswer?.reasoning_summary || "发送消息后显示"}
            </Typography.Paragraph>
            {lastAnswer?.metadata?.review_task_id ? (
              <Typography.Paragraph>
                <strong>审查任务：</strong>
                {String(lastAnswer.metadata.review_task_id)}
              </Typography.Paragraph>
            ) : null}
            {lastAnswer?.metadata?.test_generation_task_id ? (
              <Typography.Paragraph>
                <strong>测试任务：</strong>
                {String(lastAnswer.metadata.test_generation_task_id)}
              </Typography.Paragraph>
            ) : null}
            <Typography.Text type="secondary">
              置信度：{lastAnswer ? lastAnswer.confidence.toFixed(2) : "0.00"}
            </Typography.Text>
          </Card>
        </Space>
      </div>

      <Modal
        title="新建问答会话"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={submitCreateSession}
        confirmLoading={createSessionMutation.isPending}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="会话名称"
            name="title"
            rules={[
              { required: true, message: "请输入会话名称" },
              { max: 60, message: "会话名称不能超过 60 个字符" },
            ]}
          >
            <Input placeholder="例如：口腔医院项目检索模块讨论" autoFocus />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
