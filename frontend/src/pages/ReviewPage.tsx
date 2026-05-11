import { Button, Card, Drawer, Form, Input, Select, Space, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { createReviewTask, getReviewResult, getTaskStatus, listReviewTasks } from "../api/platform";
import { PageHeader } from "../components/PageHeader";
import { ResultPanel } from "../components/ResultPanel";
import { StatusTag } from "../components/StatusTag";
import { TaskTable } from "../components/TaskTable";
import { useCurrentProject } from "../hooks/useCurrentProject";
import type { ReviewResult, ReviewTask, TaskStatus } from "../types/domain";

export default function ReviewPage() {
  const { projectId } = useCurrentProject();
  const queryClient = useQueryClient();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<ReviewTask | null>(null);

  const taskQuery = useQuery({
    queryKey: ["reviews", projectId],
    queryFn: () => listReviewTasks(projectId),
    enabled: !!projectId,
  });

  const statusQuery = useQuery<TaskStatus>({
    queryKey: ["review-status", selectedTask?.id],
    queryFn: () => getTaskStatus(selectedTask!.id),
    enabled: !!selectedTask?.id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["completed", "failed"].includes(status) ? false : 2000;
    },
  });

  const resultQuery = useQuery<ReviewResult>({
    queryKey: ["review-result", selectedTask?.id, statusQuery.data?.status],
    queryFn: () => getReviewResult(selectedTask!.id),
    enabled: !!selectedTask?.id && statusQuery.data?.status === "completed",
  });

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => createReviewTask(projectId, payload),
    onSuccess: (task) => {
      setDrawerOpen(false);
      setSelectedTask(task);
      queryClient.invalidateQueries({ queryKey: ["reviews", projectId] });
    },
  });

  useEffect(() => {
    if (statusQuery.data?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["reviews", projectId] });
    }
  }, [projectId, queryClient, statusQuery.data?.status]);

  const columns: ColumnsType<ReviewTask> = [
    { title: "任务标题", dataIndex: "title" },
    { title: "语言", dataIndex: "language", width: 120 },
    { title: "来源", dataIndex: "source_type", width: 140 },
    { title: "状态", dataIndex: "status", width: 120, render: (value) => <StatusTag value={value} /> },
    { title: "阶段", dataIndex: "progress_stage", width: 180 },
  ];

  return (
    <div className="page-grid">
      <PageHeader
        title="代码审查"
        description="面向 Python / Java / JavaScript / Go 的异步 Code Review 工作台。"
        extra={<Button type="primary" onClick={() => setDrawerOpen(true)}>新建审查任务</Button>}
      />

      <div className="split-grid">
        <Card className="content-card" title="任务列表">
          <TaskTable
            columns={columns}
            dataSource={taskQuery.data ?? []}
            loading={taskQuery.isLoading}
            onRowClick={setSelectedTask}
          />
        </Card>
        <ResultPanel title={selectedTask ? `结果详情 · ${selectedTask.title}` : "结果详情"}>
          {!selectedTask ? (
            <Typography.Text type="secondary">从左侧任务列表选择一个任务以查看结果。</Typography.Text>
          ) : statusQuery.data?.status !== "completed" ? (
            <Space direction="vertical">
              <StatusTag value={statusQuery.data?.status || selectedTask.status} />
              <Typography.Text type="secondary">
                当前阶段：{statusQuery.data?.progress_stage || selectedTask.progress_stage}
              </Typography.Text>
              {statusQuery.data?.error_message ? (
                <Typography.Text type="danger">{statusQuery.data.error_message}</Typography.Text>
              ) : null}
            </Space>
          ) : (
            <Space direction="vertical" style={{ width: "100%" }} size="large">
              <div>
                <Typography.Title level={5}>审查结论</Typography.Title>
                <Typography.Paragraph>{resultQuery.data?.summary}</Typography.Paragraph>
              </div>
              <div>
                <Typography.Title level={5}>问题发现</Typography.Title>
                <Space direction="vertical" style={{ width: "100%" }}>
                  {(resultQuery.data?.findings ?? []).map((finding) => (
                    <Card
                      key={`${finding.title}-${finding.evidence}`}
                      size="small"
                      title={finding.title}
                      extra={<StatusTag value={finding.severity} />}
                    >
                      <Typography.Paragraph>
                        <strong>证据：</strong>
                        {finding.evidence}
                      </Typography.Paragraph>
                      <Typography.Paragraph>
                        <strong>影响：</strong>
                        {finding.impact}
                      </Typography.Paragraph>
                      <Typography.Paragraph>
                        <strong>建议：</strong>
                        {finding.suggestion}
                      </Typography.Paragraph>
                      {finding.example_fix ? (
                        <pre className="code-block">{finding.example_fix}</pre>
                      ) : null}
                    </Card>
                  ))}
                </Space>
              </div>
            </Space>
          )}
        </ResultPanel>
      </div>

      <Drawer
        title="发起代码审查"
        width={560}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose
      >
        <Form
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
          initialValues={{ source_type: "snippet", language: "python" }}
        >
          <Form.Item label="任务标题" name="title" rules={[{ required: true }]}>
            <Input placeholder="例如：用户服务异常处理重构审查" />
          </Form.Item>
          <Space style={{ display: "flex" }}>
            <Form.Item label="语言" name="language" rules={[{ required: true }]}>
              <Select
                style={{ width: 180 }}
                options={[
                  { value: "python", label: "Python" },
                  { value: "java", label: "Java" },
                  { value: "javascript", label: "JavaScript" },
                  { value: "go", label: "Go" },
                ]}
              />
            </Form.Item>
            <Form.Item label="来源" name="source_type" rules={[{ required: true }]}>
              <Select
                style={{ width: 180 }}
                options={[
                  { value: "snippet", label: "代码片段" },
                  { value: "manual_diff", label: "手动 Diff" },
                  { value: "github_pr", label: "GitHub PR" },
                  { value: "github_commit", label: "GitHub Commit" },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item label="代码 / Diff / PR 内容" name="content" rules={[{ required: true }]}>
            <Input.TextArea rows={14} placeholder="粘贴代码、diff 或 PR 摘要" />
          </Form.Item>
          <Button htmlType="submit" type="primary" loading={createMutation.isPending}>
            提交异步任务
          </Button>
        </Form>
      </Drawer>
    </div>
  );
}
