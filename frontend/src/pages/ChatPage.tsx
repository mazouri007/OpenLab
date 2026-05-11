import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  List,
  Modal,
  Skeleton,
  Space,
  Typography,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  createChatSession,
  listChatMessages,
  listChatSessions,
  sendChatMessage,
} from "../api/platform";
import { CitationList } from "../components/CitationList";
import { MessageContent } from "../components/MessageContent";
import { PageHeader } from "../components/PageHeader";
import { useCurrentProject } from "../hooks/useCurrentProject";
import type { ChatAnswer, ChatMessage, ChatSession } from "../types/domain";

type LocalExchange = {
  sessionId: string;
  question: string;
  answer: ChatAnswer;
};

type DisplayMessage = Pick<ChatMessage, "id" | "role" | "content" | "citations_json">;

type CreateSessionForm = {
  title: string;
};

export default function ChatPage() {
  const { projectId } = useCurrentProject();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<CreateSessionForm>();
  const [input, setInput] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [lastExchange, setLastExchange] = useState<LocalExchange | null>(null);

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

  const sendMutation = useMutation({
    mutationFn: (content: string) => sendChatMessage(selectedSession!.id, content),
    onSuccess: async (answer, question) => {
      if (selectedSession) {
        setLastExchange({ sessionId: selectedSession.id, question, answer });
      }
      setInput("");
      await queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedSession?.id] });
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", projectId] });
    },
    onError: (error: Error) => {
      message.error(`发送失败：${error.message}`);
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
        id: `local-user-${lastExchange.sessionId}`,
        role: "user",
        content: lastExchange.question,
        citations_json: [],
      });
    }
    if (!hasAnswer) {
      merged.push({
        id: `local-assistant-${lastExchange.sessionId}`,
        role: "assistant",
        content: lastExchange.answer.answer,
        citations_json: lastExchange.answer.citations,
      });
    }
    return merged;
  }, [lastExchange, messagesQuery.data, selectedSession?.id]);

  const lastAnswer =
    lastExchange && lastExchange.sessionId === selectedSession?.id ? lastExchange.answer : null;

  const submitQuestion = () => {
    const content = input.trim();
    if (!selectedSession || !content) {
      return;
    }
    sendMutation.mutate(content);
  };

  const submitCreateSession = async () => {
    const values = await form.validateFields();
    createSessionMutation.mutate(values);
  };

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
            {sendMutation.isPending ? (
              <div className="message-item assistant">
                <Typography.Text strong>AI 助手</Typography.Text>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 6 }}>
                  正在检索知识库并调用模型生成回答...
                </Typography.Paragraph>
              </div>
            ) : null}
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
          <Button
            type="primary"
            style={{ marginTop: 12 }}
            disabled={!selectedSession || !input.trim()}
            loading={sendMutation.isPending}
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
