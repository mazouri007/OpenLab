import { Button, Card, Form, Input, List, Space, Typography } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createGithubIntegration, listRepositories, syncRepositories } from "../api/platform";
import { PageHeader } from "../components/PageHeader";
import { StatusTag } from "../components/StatusTag";
import { useCurrentProject } from "../hooks/useCurrentProject";

export default function GithubPage() {
  const { projectId } = useCurrentProject();
  const queryClient = useQueryClient();

  const reposQuery = useQuery({
    queryKey: ["repos", projectId],
    queryFn: () => listRepositories(projectId),
    enabled: !!projectId,
  });

  const integrationMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => createGithubIntegration(projectId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["repos", projectId] }),
  });

  const syncMutation = useMutation({
    mutationFn: () => syncRepositories(projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["repos", projectId] }),
  });

  return (
    <div className="page-grid">
      <PageHeader
        title="GitHub 集成"
        description="配置 PAT、同步仓库，并为 PR / Commit 触发自动审查任务。"
        extra={
          <Button type="primary" onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
            同步仓库
          </Button>
        }
      />

      <div className="split-grid">
        <Card className="content-card" title="集成配置">
          <Form
            layout="vertical"
            onFinish={(values) => integrationMutation.mutate(values)}
            initialValues={{ auth_type: "pat", webhook_secret: "dev-secret" }}
          >
            <Form.Item label="认证方式" name="auth_type">
              <Input disabled />
            </Form.Item>
            <Form.Item label="Personal Access Token" name="token" rules={[{ required: true }]}>
              <Input.Password placeholder="ghp_xxx" />
            </Form.Item>
            <Form.Item label="Webhook Secret" name="webhook_secret" rules={[{ required: true }]}>
              <Input placeholder="dev-secret" />
            </Form.Item>
            <Button htmlType="submit" type="primary" loading={integrationMutation.isPending}>
              保存集成
            </Button>
          </Form>
        </Card>

        <Card className="content-card" title="仓库状态">
          <List
            dataSource={reposQuery.data ?? []}
            loading={reposQuery.isLoading}
            locale={{ emptyText: "尚未同步任何仓库" }}
            renderItem={(repo) => (
              <List.Item>
                <div>
                  <Typography.Text strong>{repo.repo_full_name}</Typography.Text>
                  <div>
                    <Typography.Text type="secondary">
                      默认分支：{repo.default_branch} · Open PR：{repo.open_pr_count}
                    </Typography.Text>
                  </div>
                  <div>
                    <Typography.Text type="secondary">
                      最近同步：{repo.last_synced_at || "未同步"}
                    </Typography.Text>
                  </div>
                </div>
                <Space>
                  <StatusTag value={repo.status} />
                </Space>
              </List.Item>
            )}
          />
        </Card>
      </div>
    </div>
  );
}
