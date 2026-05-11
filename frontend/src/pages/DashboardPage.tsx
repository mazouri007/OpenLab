import { Card, Col, List, Row, Skeleton, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";

import { listDocuments, listProviders, listRepositories, listReviewTasks, listTestTasks } from "../api/platform";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusTag } from "../components/StatusTag";
import { useCurrentProject } from "../hooks/useCurrentProject";

export default function DashboardPage() {
  const { projectId, currentProject } = useCurrentProject();
  const reviewQuery = useQuery({
    queryKey: ["reviews", projectId],
    queryFn: () => listReviewTasks(projectId),
    enabled: !!projectId,
  });
  const testQuery = useQuery({
    queryKey: ["test-tasks", projectId],
    queryFn: () => listTestTasks(projectId),
    enabled: !!projectId,
  });
  const docsQuery = useQuery({
    queryKey: ["docs", projectId],
    queryFn: () => listDocuments(projectId),
    enabled: !!projectId,
  });
  const reposQuery = useQuery({
    queryKey: ["repos", projectId],
    queryFn: () => listRepositories(projectId),
    enabled: !!projectId,
  });
  const providerQuery = useQuery({
    queryKey: ["providers", projectId],
    queryFn: () => listProviders(projectId),
    enabled: !!projectId,
  });

  const loading =
    reviewQuery.isLoading ||
    testQuery.isLoading ||
    docsQuery.isLoading ||
    reposQuery.isLoading ||
    providerQuery.isLoading;

  return (
    <div className="page-grid">
      <PageHeader
        title="项目总览"
        description={`当前项目：${currentProject?.name ?? "默认项目"}，聚合查看 AI 审查、测试、知识库和模型状态。`}
      />

      {loading ? <Skeleton active /> : null}

      <Row gutter={16}>
        <Col span={6}>
          <MetricCard title="Code Review 任务" value={reviewQuery.data?.length ?? 0} />
        </Col>
        <Col span={6}>
          <MetricCard title="TestGen 任务" value={testQuery.data?.length ?? 0} />
        </Col>
        <Col span={6}>
          <MetricCard title="知识库文档" value={docsQuery.data?.length ?? 0} />
        </Col>
        <Col span={6}>
          <MetricCard title="GitHub 仓库" value={reposQuery.data?.length ?? 0} />
        </Col>
      </Row>

      <div className="split-grid">
        <Card className="content-card" title="最近 Code Review">
          <List
            dataSource={(reviewQuery.data ?? []).slice(0, 5)}
            locale={{ emptyText: "暂无审查任务" }}
            renderItem={(item) => (
              <List.Item>
                <div>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <div>
                    <Typography.Text type="secondary">
                      {item.language} / {item.source_type}
                    </Typography.Text>
                  </div>
                </div>
                <StatusTag value={item.status} />
              </List.Item>
            )}
          />
        </Card>
        <Card className="content-card" title="模型与知识库状态">
          <List
            dataSource={[
              `默认模型供应商：${providerQuery.data?.[0]?.name ?? "未配置"}`,
              `Embedding 模型：${providerQuery.data?.[0]?.default_embedding_model ?? "未配置"}`,
              `已索引文档：${(docsQuery.data ?? []).filter((doc) => doc.parse_status === "indexed").length}`,
              `仓库同步状态：${reposQuery.data?.length ? "已接入" : "未接入"}`,
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>
      </div>
    </div>
  );
}
