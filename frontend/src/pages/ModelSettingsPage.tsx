import { Alert, App as AntApp, Button, Card, Form, Input, List, Select, Space, Switch } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createProvider, listProviders, testProvider } from "../api/platform";
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
  is_default: boolean;
};

export default function ModelSettingsPage() {
  const { projectId, isLoading: isProjectLoading } = useCurrentProject();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<ProviderFormValues>();
  const projectReady = Boolean(projectId);

  const providerQuery = useQuery({
    queryKey: ["providers", projectId],
    queryFn: () => listProviders(projectId),
    enabled: projectReady,
  });

  const createMutation = useMutation({
    mutationFn: (payload: ProviderFormValues) => createProvider(projectId, { ...payload }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["providers", projectId] });
      message.success("模型配置已保存到当前项目。");
    },
    onError: (error: Error) => {
      message.error(`保存失败：${error.message}`);
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

  const validateProject = () => {
    if (!projectReady) {
      message.warning("项目尚未加载完成，请稍后再试。");
      return false;
    }
    return true;
  };

  const submitSave = async () => {
    if (!validateProject()) {
      return;
    }
    const values = await form.validateFields();
    createMutation.mutate(values);
  };

  const submitTest = async () => {
    if (!validateProject()) {
      return;
    }
    const values = await form.validateFields();
    testMutation.mutate(values);
  };

  return (
    <div className="page-grid">
      <PageHeader
        title="模型配置"
        description="基于 LiteLLM 接入 OpenAI-Compatible provider，并指定默认 chat / embedding 模型。"
      />

      <div className="split-grid">
        <Card className="content-card" title="新增模型供应商">
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
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              provider_type: "openai-compatible",
              is_default: true,
              base_url: "https://ai.centos.hk/v1",
              default_chat_model: "glm-4-flash",
              default_embedding_model: "embedding-3",
            }}
          >
            <Form.Item label="显示名称" name="name" rules={[{ required: true }]}>
              <Input placeholder="实验室默认模型" />
            </Form.Item>
            <Form.Item label="供应商类型" name="provider_type" rules={[{ required: true }]}>
              <Select options={[{ value: "openai-compatible", label: "OpenAI-Compatible" }]} />
            </Form.Item>
            <Form.Item label="Base URL" name="base_url" rules={[{ required: true }]}>
              <Input placeholder="https://ai.centos.hk/v1 或 https://open.bigmodel.cn/api/paas/v4" />
            </Form.Item>
            <Form.Item label="API Key" name="api_key" rules={[{ required: true }]}>
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item label="Chat Model" name="default_chat_model" rules={[{ required: true }]}>
              <Input placeholder="glm-4-flash / gpt-4o-mini / deepseek-chat" />
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
                onClick={submitSave}
                loading={createMutation.isPending}
                disabled={!projectReady}
              >
                保存配置
              </Button>
              <Button
                onClick={submitTest}
                loading={testMutation.isPending}
                disabled={!projectReady}
              >
                测试连通
              </Button>
            </Space>
          </Form>
        </Card>
        <Card className="content-card" title="已配置供应商">
          <List
            loading={providerQuery.isLoading}
            dataSource={providerQuery.data ?? []}
            locale={{ emptyText: "尚未配置模型供应商" }}
            renderItem={(provider) => (
              <List.Item extra={<StatusTag value={provider.is_default ? "completed" : "info"} />}>
                <List.Item.Meta
                  title={provider.name}
                  description={
                    <div>
                      <div>
                        {provider.default_chat_model} / {provider.default_embedding_model}
                      </div>
                      <div>{provider.base_url || "未配置 Base URL"}</div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      </div>
    </div>
  );
}
