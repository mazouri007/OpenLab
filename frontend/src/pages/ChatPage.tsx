import {
  InfoCircleOutlined,
  PlusOutlined,
  SendOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Checkbox,
  Drawer,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Select,
  Skeleton,
  Space,
  Tooltip,
  Typography,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

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

type AnswerContext = {
  citations: ChatAnswer["citations"];
  rewrittenQueries: string[];
  usedMemory: string[];
  reasoningSummary: string;
  confidence: number | null;
  metadata: Record<string, unknown>;
};

type CreateSessionForm = {
  title: string;
};

type CommitIntent = "auto" | "explain" | "compliance" | "review";
type ChatAction = "auto" | "answer" | "review" | "test" | "review_and_test";

function getMessageRoleClass(role: string) {
  return role === "user" ? "user" : "assistant";
}

function getMessageLabel(role: string) {
  if (role === "user") {
    return "你";
  }
  if (role === "assistant") {
    return "OpenLab";
  }
  return role;
}

function getMessageInitial(role: string) {
  return role === "user" ? "你" : "AI";
}

function normalizeCitations(citations: Record<string, unknown>[]): ChatAnswer["citations"] {
  return citations
    .map((item) => ({
      chunk_id: String(item.chunk_id ?? item.id ?? ""),
      snippet: String(item.snippet ?? ""),
      source_type: String(item.source_type ?? "knowledge"),
      source_title:
        typeof item.source_title === "string"
          ? item.source_title
          : typeof item.source === "string"
            ? item.source
            : null,
    }))
    .filter((item) => item.chunk_id || item.snippet || item.source_title);
}

export default function ChatPage() {
  const { projectId } = useCurrentProject();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<CreateSessionForm>();
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const [input, setInput] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false);
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
  const [answerContext, setAnswerContext] = useState<AnswerContext | null>(null);

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

  useEffect(() => {
    const scrollArea = messageScrollRef.current;
    if (!scrollArea) {
      return;
    }
    scrollArea.scrollTo({
      top: scrollArea.scrollHeight,
      behavior: isStreaming ? "smooth" : "auto",
    });
  }, [displayedMessages, isStreaming]);

  const getLocalAnswerForMessage = (chatMessage: DisplayMessage) => {
    if (
      !lastExchange ||
      lastExchange.sessionId !== selectedSession?.id ||
      chatMessage.role !== "assistant"
    ) {
      return null;
    }
    if (
      chatMessage.id === `local-assistant-${lastExchange.id}` ||
      chatMessage.content === lastExchange.answer.answer
    ) {
      return lastExchange.answer;
    }
    return null;
  };

  const openAnswerContext = (chatMessage: DisplayMessage) => {
    const localAnswer = getLocalAnswerForMessage(chatMessage);
    setAnswerContext({
      citations: localAnswer?.citations ?? normalizeCitations(chatMessage.citations_json),
      rewrittenQueries: localAnswer?.rewritten_queries ?? [],
      usedMemory: localAnswer?.used_memory ?? [],
      reasoningSummary: localAnswer?.reasoning_summary ?? "",
      confidence: typeof localAnswer?.confidence === "number" ? localAnswer.confidence : null,
      metadata: localAnswer?.metadata ?? {},
    });
  };

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

  const selectSession = (session: ChatSession) => {
    setSelectedSession(session);
    setLastExchange(null);
    setSessionDrawerOpen(false);
  };

  const canSubmit =
    !!selectedSession &&
    !!input.trim() &&
    (!commitEnabled || (!!commitRepositoryId && (!!commitSha.trim() || !!prNumber)));

  return (
    <div className="page-grid chat-page">
      <PageHeader
        title="知识问答"
        description="结合项目知识库、短期摘要与长期记忆进行研发问答，并返回引用证据。"
        extra={
          <Space wrap>
            <Button
              icon={<UnorderedListOutlined />}
              onClick={() => setSessionDrawerOpen(true)}
              disabled={!projectId}
            >
              会话列表
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                form.setFieldsValue({ title: `研发问答 ${new Date().toLocaleString()}` });
                setCreateOpen(true);
              }}
              disabled={!projectId}
            >
              新建会话
            </Button>
          </Space>
        }
      />

      <div className="chat-layout">
        <Card className="content-card chat-thread-card" title={selectedSession?.title ?? "会话"}>
          <div className="chat-thread-shell">
            {!selectedSession ? (
              <div className="chat-inline-state">
                <Alert showIcon type="info" message="请先新建或选择一个会话。" />
              </div>
            ) : null}
            {messagesQuery.isLoading ? (
              <div className="chat-inline-state">
                <Skeleton active />
              </div>
            ) : null}

            <div className="message-list chat-message-scroll" ref={messageScrollRef}>
              {!messagesQuery.isLoading && selectedSession && displayedMessages.length === 0 ? (
                <div className="chat-empty-state">还没有消息</div>
              ) : null}
              {displayedMessages.map((chatMessage) => {
                const roleClass = getMessageRoleClass(chatMessage.role);
                return (
                  <div key={chatMessage.id} className={`message-row ${roleClass}`}>
                    <div className="message-avatar">{getMessageInitial(chatMessage.role)}</div>
                    <div className="message-bubble">
                      <div className="message-author">{getMessageLabel(chatMessage.role)}</div>
                      <MessageContent content={chatMessage.content} />
                      {chatMessage.role === "assistant" ? (
                        <div className="message-tools">
                          <Tooltip title="查看这次回答的引用来源、摘要与记忆">
                            <Button
                              type="text"
                              size="small"
                              icon={<InfoCircleOutlined />}
                              onClick={() => openAnswerContext(chatMessage)}
                            >
                              依据与记忆
                            </Button>
                          </Tooltip>
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="chat-composer">
              <div className="chat-composer-box">
                <Input.TextArea
                  className="chat-composer-input"
                  value={input}
                  autoSize={{ minRows: 2, maxRows: 7 }}
                  placeholder="询问实验室规范、历史 review、项目约定或测试策略"
                  onChange={(event) => setInput(event.target.value)}
                  onPressEnter={(event) => {
                    if (!event.shiftKey) {
                      event.preventDefault();
                      submitQuestion();
                    }
                  }}
                />

                {commitEnabled ? (
                  <div className="commit-context-panel chat-commit-grid">
                    <Select
                      showSearch
                      className="chat-repo-select"
                      placeholder="选择仓库"
                      options={repoOptions}
                      loading={reposQuery.isLoading}
                      value={commitRepositoryId}
                      optionFilterProp="label"
                      onChange={setCommitRepositoryId}
                    />
                    <Input
                      className="chat-sha-input"
                      placeholder="commit SHA"
                      value={commitSha}
                      onChange={(event) => setCommitSha(event.target.value)}
                    />
                    <InputNumber
                      className="chat-pr-input"
                      min={1}
                      precision={0}
                      placeholder="PR 编号"
                      value={prNumber}
                      onChange={setPrNumber}
                    />
                    <Select<CommitIntent>
                      className="chat-intent-select"
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
                      className="chat-language-select"
                      placeholder="语言"
                      value={language}
                      onChange={setLanguage}
                      options={[
                        { value: "python", label: "Python" },
                        { value: "java", label: "Java" },
                      ]}
                    />
                    <Input
                      className="chat-framework-input"
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
                  </div>
                ) : null}

                <div className="chat-composer-actions">
                  <Space wrap size="middle">
                    <Select<ChatAction>
                      className="chat-action-select"
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
                    <Checkbox
                      checked={commitEnabled}
                      onChange={(event) => setCommitEnabled(event.target.checked)}
                    >
                      GitHub 上下文
                    </Checkbox>
                  </Space>
                  <Tooltip title="发送问题">
                    <Button
                      type="primary"
                      shape="circle"
                      className="chat-send-button"
                      aria-label="发送问题"
                      icon={<SendOutlined />}
                      disabled={!canSubmit}
                      loading={isStreaming}
                      onClick={submitQuestion}
                    />
                  </Tooltip>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Drawer
        title="会话列表"
        placement="left"
        open={sessionDrawerOpen}
        width="min(340px, 100vw)"
        getContainer={false}
        rootStyle={{ position: "absolute" }}
        className="chat-session-drawer"
        onClose={() => setSessionDrawerOpen(false)}
      >
        <List
          className="chat-session-list"
          loading={sessionsQuery.isLoading}
          dataSource={sessionsQuery.data ?? []}
          locale={{ emptyText: "暂无会话，请先新建会话" }}
          renderItem={(item) => (
            <List.Item
              className={`chat-session-item ${selectedSession?.id === item.id ? "active" : ""}`}
              onClick={() => selectSession(item)}
            >
              <Typography.Text strong className="chat-session-title">
                {item.title}
              </Typography.Text>
              <Typography.Text type="secondary" className="chat-session-status">
                {item.status}
              </Typography.Text>
            </List.Item>
          )}
        />
      </Drawer>

      <Drawer
        title="回答相关信息"
        open={!!answerContext}
        width="min(420px, 100vw)"
        onClose={() => setAnswerContext(null)}
      >
        {answerContext ? (
          <div className="answer-context-content">
            <section>
              <Typography.Title level={5}>引用来源</Typography.Title>
              <CitationList citations={answerContext.citations} />
            </section>
            <section className="answer-context-section">
              <Typography.Title level={5}>摘要与记忆</Typography.Title>
              <Typography.Paragraph>
                <strong>重写查询：</strong>
                {answerContext.rewrittenQueries.join(" / ") || "暂无"}
              </Typography.Paragraph>
              <Typography.Paragraph>
                <strong>长期记忆：</strong>
                {answerContext.usedMemory.join("；") || "暂无召回"}
              </Typography.Paragraph>
              <Typography.Paragraph>
                <strong>推理摘要：</strong>
                {answerContext.reasoningSummary || "暂无"}
              </Typography.Paragraph>
              {answerContext.metadata.review_task_id ? (
                <Typography.Paragraph>
                  <strong>审查任务：</strong>
                  {String(answerContext.metadata.review_task_id)}
                </Typography.Paragraph>
              ) : null}
              {answerContext.metadata.test_generation_task_id ? (
                <Typography.Paragraph>
                  <strong>测试任务：</strong>
                  {String(answerContext.metadata.test_generation_task_id)}
                </Typography.Paragraph>
              ) : null}
              <Typography.Text type="secondary">
                置信度：
                {answerContext.confidence === null ? "暂无" : answerContext.confidence.toFixed(2)}
              </Typography.Text>
            </section>
          </div>
        ) : null}
      </Drawer>

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
