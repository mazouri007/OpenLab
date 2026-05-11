import { Button, Card, Drawer, Form, Input, Select, Space, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { createTestTask, getTaskStatus, getTestResult, listTestTasks } from "../api/platform";
import { PageHeader } from "../components/PageHeader";
import { ResultPanel } from "../components/ResultPanel";
import { StatusTag } from "../components/StatusTag";
import { TaskTable } from "../components/TaskTable";
import { useCurrentProject } from "../hooks/useCurrentProject";
import type { TaskStatus, TestResult, TestTask } from "../types/domain";

export default function TestGenPage() {
  const { projectId } = useCurrentProject();
  const queryClient = useQueryClient();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TestTask | null>(null);

  const tasksQuery = useQuery({
    queryKey: ["test-tasks", projectId],
    queryFn: () => listTestTasks(projectId),
    enabled: !!projectId,
  });
  const statusQuery = useQuery<TaskStatus>({
    queryKey: ["test-status", selectedTask?.id],
    queryFn: () => getTaskStatus(selectedTask!.id),
    enabled: !!selectedTask?.id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["completed", "failed"].includes(status) ? false : 2000;
    },
  });
  const resultQuery = useQuery<TestResult>({
    queryKey: ["test-result", selectedTask?.id, statusQuery.data?.status],
    queryFn: () => getTestResult(selectedTask!.id),
    enabled: !!selectedTask?.id && statusQuery.data?.status === "completed",
  });

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => createTestTask(projectId, payload),
    onSuccess: (task) => {
      setDrawerOpen(false);
      setSelectedTask(task);
      queryClient.invalidateQueries({ queryKey: ["test-tasks", projectId] });
    },
  });

  useEffect(() => {
    if (statusQuery.data?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["test-tasks", projectId] });
    }
  }, [projectId, queryClient, statusQuery.data?.status]);

  const columns: ColumnsType<TestTask> = [
    { title: "目标", dataIndex: "target_name" },
    { title: "语言", dataIndex: "language", width: 100 },
    { title: "框架", dataIndex: "framework", width: 120 },
    { title: "状态", dataIndex: "status", width: 120, render: (value) => <StatusTag value={value} /> },
    { title: "阶段", dataIndex: "progress_stage", width: 180 },
  ];

  return (
    <div className="page-grid">
      <PageHeader
        title="测试生成"
        description="针对 Python / Java 方法生成可直接运行的单元测试，并提供自检状态。"
        extra={<Button type="primary" onClick={() => setDrawerOpen(true)}>新建测试任务</Button>}
      />

      <div className="split-grid">
        <Card className="content-card" title="任务列表">
          <TaskTable
            columns={columns}
            dataSource={tasksQuery.data ?? []}
            loading={tasksQuery.isLoading}
            onRowClick={setSelectedTask}
          />
        </Card>
        <ResultPanel title={selectedTask ? `测试结果 · ${selectedTask.target_name}` : "测试结果"}>
          {!selectedTask ? (
            <Typography.Text type="secondary">选择一个测试任务后展示结果代码与场景覆盖。</Typography.Text>
          ) : statusQuery.data?.status !== "completed" ? (
            <Space direction="vertical">
              <StatusTag value={statusQuery.data?.status || selectedTask.status} />
              <Typography.Text type="secondary">
                当前阶段：{statusQuery.data?.progress_stage || selectedTask.progress_stage}
              </Typography.Text>
            </Space>
          ) : (
            <Space direction="vertical" style={{ width: "100%" }} size="large">
              <div>
                <Typography.Title level={5}>覆盖场景</Typography.Title>
                {(resultQuery.data?.scenarios ?? []).map((scenario) => (
                  <Card
                    key={`${scenario.name}-${scenario.case_type}`}
                    size="small"
                    title={scenario.name}
                    extra={<StatusTag value={scenario.case_type} />}
                    style={{ marginBottom: 12 }}
                  >
                    {scenario.description}
                  </Card>
                ))}
              </div>
              <div>
                <Typography.Title level={5}>生成代码</Typography.Title>
                <pre className="code-block">{resultQuery.data?.test_code}</pre>
              </div>
              <div>
                <Typography.Title level={5}>自检状态</Typography.Title>
                <pre className="code-block">
                  {JSON.stringify(resultQuery.data?.self_check_report ?? {}, null, 2)}
                </pre>
              </div>
            </Space>
          )}
        </ResultPanel>
      </div>

      <Drawer
        title="生成单元测试"
        width={560}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose
      >
        <Form
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
          initialValues={{ language: "python", framework: "pytest" }}
        >
          <Form.Item label="语言" name="language" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "python", label: "Python" },
                { value: "java", label: "Java" },
              ]}
            />
          </Form.Item>
          <Form.Item label="测试框架" name="framework" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "pytest", label: "pytest" },
                { value: "junit5", label: "JUnit 5" },
              ]}
            />
          </Form.Item>
          <Form.Item label="目标函数 / 方法" name="target_name" rules={[{ required: true }]}>
            <Input placeholder="例如：calculate_discount" />
          </Form.Item>
          <Form.Item label="源代码" name="code" rules={[{ required: true }]}>
            <Input.TextArea rows={14} placeholder="粘贴函数或类方法源码" />
          </Form.Item>
          <Form.Item label="补充要求" name="extra_requirements">
            <Input.TextArea rows={4} placeholder="例如：需要覆盖权限校验、异常分支和边界值" />
          </Form.Item>
          <Button htmlType="submit" type="primary" loading={createMutation.isPending}>
            提交异步任务
          </Button>
        </Form>
      </Drawer>
    </div>
  );
}
