import { Button, Card, Form, Input, List } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createDocument, listDocuments } from "../api/platform";
import { PageHeader } from "../components/PageHeader";
import { StatusTag } from "../components/StatusTag";
import { useCurrentProject } from "../hooks/useCurrentProject";

export default function KnowledgePage() {
  const { projectId } = useCurrentProject();
  const queryClient = useQueryClient();
  const docsQuery = useQuery({
    queryKey: ["docs", projectId],
    queryFn: () => listDocuments(projectId),
    enabled: !!projectId,
    refetchInterval: 4000,
  });

  const uploadMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => createDocument(projectId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["docs", projectId] }),
  });

  return (
    <div className="page-grid">
      <PageHeader
        title="知识库"
        description="导入研发规范、历史案例和 FAQ，构建支持引用回答的检索增强知识库。"
      />

      <div className="split-grid">
        <Card className="content-card" title="上传与索引">
          <Form
            layout="vertical"
            onFinish={(values) =>
              uploadMutation.mutate({
                ...values,
                source_type: "text",
                source_name: "manual-entry",
              })
            }
          >
            <Form.Item label="文档标题" name="title" rules={[{ required: true }]}>
              <Input placeholder="实验室 Java Code Review Checklist" />
            </Form.Item>
            <Form.Item label="文档内容" name="raw_text" rules={[{ required: true }]}>
              <Input.TextArea rows={14} placeholder="粘贴规范、FAQ、历史案例等文本内容" />
            </Form.Item>
            <Button htmlType="submit" type="primary" loading={uploadMutation.isPending}>
              上传并索引
            </Button>
          </Form>
        </Card>

        <Card className="content-card" title="文档列表">
          <List
            dataSource={docsQuery.data ?? []}
            loading={docsQuery.isLoading}
            locale={{ emptyText: "暂无文档" }}
            renderItem={(doc) => (
              <List.Item extra={<StatusTag value={doc.parse_status} />}>
                <List.Item.Meta title={doc.title} description={`来源类型：${doc.source_type}`} />
              </List.Item>
            )}
          />
        </Card>
      </div>
    </div>
  );
}
