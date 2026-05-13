import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  List,
  Modal,
  Select,
  Space,
  Switch,
  Typography,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createProvider,
  listProviders,
  testProvider,
  updateProvider,
  updateProviderSecrets,
} from "../api/platform";
import { PageHeader } from "../components/PageHeader";
import { StatusTag } from "../components/StatusTag";
import { useCurrentProject } from "../hooks/useCurrentProject";

type ProviderFormValues = {
  name: string;
  provider_type: string;
  base_url: string;
  api_key: string;
  default_chat_model: string;
  default_embedding_model: string;
  embedding_provider_type?: string;
  embedding_base_url?: string;
  embedding_api_key?: string;
  is_default: boolean;
};

type ProviderSecretFormValues = {
  api_key?: string;
  embedding_api_key?: string;
};

export default function ModelSettingsPage() {
  const { projectId, isLoading: isProjectLoading } = useCurrentProject();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<ProviderFormValues>();
  const [secretForm] = Form.useForm<ProviderSecretFormValues>();
  const [secretProviderId, setSecretProviderId] = useState<string | null>(null);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const projectReady = Boolean(projectId);

  const providerQuery = useQuery({
    queryKey: ["providers", projectId],
    queryFn: () => listProviders(projectId),
    enabled: projectReady,
  });

  const chatSaveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      editingProviderId
        ? updateProvider(projectId, editingProviderId, payload)
        : createProvider(projectId, payload),
    onSuccess: async (provider) => {
      setEditingProviderId(provider.id);
      await queryClient.invalidateQueries({ queryKey: ["providers", projectId] });
      message.success("Chat 配置已保存。");
    },
    onError: (error: Error) => {
      message.error(`Chat 配置保存失败：${error.message}`);
    },
  });

  const embeddingSaveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      updateProvider(projectId, editingProviderId!, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["providers", projectId] });
      message.success("Embedding 配置已保存。");
    },
    onError: (error: Error) => {
      message.error(`Embedding 配置保存失败：${error.message}`);
    },
  });

  const testMutation = useMutation({
    mutationFn: (payload: ProviderFormValues) => testProvider(projectId, { ...payload }),
    onSuccess: (data) => {
      message.success(`连通成功：${data.model}`);
    },
    onError: (error: Error) => {
      message.error(`连通失败：${error.message}`);
    },
  });

  const secretMutation = useMutation({
    mutationFn: (payload: ProviderSecretFormValues) =>
      updateProviderSecrets(projectId, secretProviderId!, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["providers", projectId] });
      secretForm.resetFields();
      setSecretProviderId(null);
      message.success("模型密钥已更新。");
    },
    onError: (error: Error) => {
      message.error(`密钥更新失败：${error.message}`);
    },
  });

  const validateProject = () => {
    if (!projectReady) {
      message.warning("项目尚未加载完成，请稍后再试。");
      return false;
    }
    return true;
  };

  const submitChatSave = async () => {
    if (!validateProject()) {
      return;
    }
    const fields: (keyof ProviderFormValues)[] = [
      "name",
      "provider_type",
      "base_url",
      "default_chat_model",
      "is_default",
    ];
    if (!editingProviderId) {
      fields.push("api_key");
    }
    const values = await form.validateFields(fields);
    const payload: Record<string, unknown> = {
      name: values.name,
      provider_type: values.provider_type,
      base_url: values.base_url,
      default_chat_model: values.default_chat_model,
      is_default: values.is_default,
    };
    const apiKey = form.getFieldValue("api_key");
    if (typeof apiKey === "string" && apiKey.trim()) {
      payload.api_key = apiKey.trim();
    }
    if (!editingProviderId) {
      payload.default_embedding_model =
        form.getFieldValue("default_embedding_model") || "text-embedding-3-small";
    }
    chatSaveMutation.mutate(payload);
  };

  const submitEmbeddingSave = async () => {
    if (!validateProject()) {
      return;
    }
    if (!editingProviderId) {
      message.warning("请先保存 Chat 配置，再单独保存 Embedding 配置。");
      return;
    }
    const values = await form.validateFields(["default_embedding_model"]);
    const payload: Record<string, unknown> = {
      default_embedding_model: values.default_embedding_model,
      embedding_provider_type: form.getFieldValue("embedding_provider_type") || null,
      embedding_base_url: form.getFieldValue("embedding_base_url") || null,
    };
    const embeddingApiKey = form.getFieldValue("embedding_api_key");
    if (typeof embeddingApiKey === "string" && embeddingApiKey.trim()) {
      payload.embedding_api_key = embeddingApiKey.trim();
    }
    embeddingSaveMutation.mutate(payload);
  };

  const submitTest = async () => {
    if (!validateProject()) {
      return;
    }
    const values = await form.validateFields();
    testMutation.mutate(values);
  };

  const submitSecrets = async () => {
    const values = await secretForm.validateFields();
    const payload = Object.fromEntries(
      Object.entries(values).filter(([, value]) => typeof value === "string" && value.trim()),
    );
    if (!Object.keys(payload).length) {
      message.warning("请输入至少一个新密钥。");
      return;
    }
    secretMutation.mutate(payload);
  };

  return (
    <div className="page-grid">
      <PageHeader
        title="模型配置"
        description="基于 LangChain 模型层接入 OpenAI-Compatible provider，并可为 Chat 与 Embedding 分别配置地址和密钥。"
      />

      <div className="split-grid">
        <Card className="content-card" title={editingProviderId ? "编辑模型供应商" : "新增模型供应商"}>
          {!projectReady ? (
            <Alert
              showIcon
              type="warning"
              style={{ marginBottom: 16 }}
              message={isProjectLoading ? "正在加载项目，请稍后。" : "当前没有可用项目。"}
            />
          ) : null}
          <Alert
            showIcon
            type="info"
            style={{ marginBottom: 16 }}
            message="保存配置只负责落库；连通性是否可用，需要点击“测试连通”或在 Review / Chat 中实际调用后端。"
          />
          {editingProviderId ? (
            <Alert
              showIcon
              type="success"
              style={{ marginBottom: 16 }}
              message="正在编辑已保存的模型供应商；Chat 与 Embedding 配置可以分别保存。"
            />
          ) : null}
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              provider_type: "openai-compatible",
              is_default: true,
              base_url: "https://ai.centos.hk/v1",
              default_chat_model: "glm-4-flash",
              embedding_provider_type: "openai-compatible",
              default_embedding_model: "embedding-3",
            }}
          >
            <Form.Item label="显示名称" name="name" rules={[{ required: true }]}>
              <Input placeholder="实验室默认模型" />
            </Form.Item>
            <Form.Item label="供应商类型" name="provider_type" rules={[{ required: true }]}>
              <Select options={[{ value: "openai-compatible", label: "OpenAI-Compatible" }]} />
            </Form.Item>
            <Typography.Title level={5}>Chat 配置</Typography.Title>
            <Form.Item label="Base URL" name="base_url" rules={[{ required: true }]}>
              <Input placeholder="https://ai.centos.hk/v1 或 https://open.bigmodel.cn/api/paas/v4" />
            </Form.Item>
            <Form.Item
              label="API Key"
              name="api_key"
              rules={[{ required: !editingProviderId, message: "新建 Chat 配置时需要 API Key" }]}
            >
              <Input.Password placeholder={editingProviderId ? "留空则不修改 Chat API Key" : "sk-..."} />
            </Form.Item>
            <Form.Item label="Chat Model" name="default_chat_model" rules={[{ required: true }]}>
              <Input placeholder="glm-4-flash / gpt-4o-mini / deepseek-chat" />
            </Form.Item>
            <Typography.Title level={5}>Embedding 配置</Typography.Title>
            <Form.Item label="Embedding 供应商类型" name="embedding_provider_type">
              <Select
                allowClear
                options={[{ value: "openai-compatible", label: "OpenAI-Compatible" }]}
                placeholder="默认沿用 Chat 供应商类型"
              />
            </Form.Item>
            <Form.Item label="Embedding Base URL" name="embedding_base_url">
              <Input placeholder="不填则沿用 Chat Base URL" />
            </Form.Item>
            <Form.Item label="Embedding API Key" name="embedding_api_key">
              <Input.Password placeholder="不填则沿用 Chat API Key" />
            </Form.Item>
            <Form.Item
              label="Embedding Model"
              name="default_embedding_model"
              rules={[{ required: true }]}
            >
              <Input placeholder="embedding-3 / text-embedding-3-small" />
            </Form.Item>
            <Form.Item label="设为默认" name="is_default" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Space>
              <Button
                type="primary"
                onClick={submitChatSave}
                loading={chatSaveMutation.isPending}
                disabled={!projectReady}
              >
                保存 Chat 配置
              </Button>
              <Button
                onClick={submitEmbeddingSave}
                loading={embeddingSaveMutation.isPending}
                disabled={!projectReady || !editingProviderId}
              >
                保存 Embedding 配置
              </Button>
              <Button
                onClick={submitTest}
                loading={testMutation.isPending}
                disabled={!projectReady}
              >
                测试连通
              </Button>
              {editingProviderId ? (
                <Button
                  onClick={() => {
                    setEditingProviderId(null);
                    form.resetFields();
                  }}
                >
                  新建配置
                </Button>
              ) : null}
            </Space>
          </Form>
        </Card>
        <Card className="content-card" title="已配置供应商">
          <List
            loading={providerQuery.isLoading}
            dataSource={providerQuery.data ?? []}
            locale={{ emptyText: "尚未配置模型供应商" }}
            renderItem={(provider) => (
              <List.Item
                extra={
                  <Space>
                    <StatusTag value={provider.is_default ? "completed" : "info"} />
                    <Button
                      size="small"
                      onClick={() => {
                        setEditingProviderId(provider.id);
                        form.setFieldsValue({
                          name: provider.name,
                          provider_type: provider.provider_type,
                          base_url: provider.base_url || "",
                          api_key: "",
                          default_chat_model: provider.default_chat_model,
                          embedding_provider_type:
                            provider.embedding_provider_type || provider.provider_type,
                          embedding_base_url: provider.embedding_base_url || "",
                          embedding_api_key: "",
                          default_embedding_model: provider.default_embedding_model,
                          is_default: provider.is_default,
                        });
                      }}
                    >
                      编辑配置
                    </Button>
                    <Button
                      size="small"
                      onClick={() => {
                        setSecretProviderId(provider.id);
                        secretForm.resetFields();
                      }}
                    >
                      更新密钥
                    </Button>
                  </Space>
                }
              >
                <List.Item.Meta
                  title={provider.name}
                  description={
                    <div>
                      <div>
                        {provider.default_chat_model} / {provider.default_embedding_model}
                      </div>
                      <div>{provider.base_url || "未配置 Base URL"}</div>
                      <div>
                        Embedding: {provider.embedding_base_url || provider.base_url || "未配置 Base URL"}
                      </div>
                      <div>
                        Chat Key: {provider.has_api_key ? provider.api_key_masked || "已配置" : "未配置"}
                      </div>
                      <div>
                        Embedding Key:{" "}
                        {provider.has_embedding_api_key
                          ? provider.embedding_api_key_masked || "已配置"
                          : "沿用 Chat Key 或未配置"}
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      </div>

      <Modal
        title="更新模型密钥"
        open={!!secretProviderId}
        onCancel={() => setSecretProviderId(null)}
        onOk={submitSecrets}
        confirmLoading={secretMutation.isPending}
        okText="更新"
        cancelText="取消"
      >
        <Form form={secretForm} layout="vertical">
          <Form.Item label="Chat API Key" name="api_key">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Form.Item label="Embedding API Key" name="embedding_api_key">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
