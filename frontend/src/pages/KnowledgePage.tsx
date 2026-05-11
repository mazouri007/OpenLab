import { InboxOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, List, Space, Typography, Upload } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { UploadFile } from "antd";

import { createDocument, listDocuments, uploadDocument } from "../api/platform";
import { PageHeader } from "../components/PageHeader";
import { StatusTag } from "../components/StatusTag";
import { useCurrentProject } from "../hooks/useCurrentProject";

export default function KnowledgePage() {
  const { projectId } = useCurrentProject();
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
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

  const fileUploadMutation = useMutation({
    mutationFn: (payload: { file: File; title?: string }) => uploadDocument(projectId, payload),
    onSuccess: () => {
      setSelectedFile(null);
      setFileList([]);
      queryClient.invalidateQueries({ queryKey: ["docs", projectId] });
    },
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
            onFinish={(values) => {
              if (!selectedFile) {
                return;
              }
              fileUploadMutation.mutate({
                file: selectedFile,
                title: values.file_title,
              });
            }}
          >
            <Form.Item label="文件标题" name="file_title">
              <Input placeholder="不填写则使用文件名" />
            </Form.Item>
            <Form.Item
              label="文档文件"
              required
              validateStatus={!selectedFile && fileUploadMutation.isError ? "error" : undefined}
              help={!selectedFile && fileUploadMutation.isError ? "请选择要上传的文件" : undefined}
            >
              <Upload.Dragger
                accept=".pdf,.docx,.xlsx,.csv,.txt,.md"
                beforeUpload={(file) => {
                  setSelectedFile(file);
                  setFileList([file]);
                  return false;
                }}
                fileList={fileList}
                maxCount={1}
                onRemove={() => {
                  setSelectedFile(null);
                  setFileList([]);
                }}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">上传 PDF、Word、Excel、CSV、TXT 或 Markdown</p>
              </Upload.Dragger>
            </Form.Item>
            {fileUploadMutation.isError ? (
              <Alert
                type="error"
                showIcon
                message={fileUploadMutation.error.message}
                style={{ marginBottom: 12 }}
              />
            ) : null}
            <Button
              htmlType="submit"
              type="primary"
              loading={fileUploadMutation.isPending}
              disabled={!selectedFile}
            >
              上传文件并索引
            </Button>
          </Form>

          <div className="form-divider" />

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
                <List.Item.Meta
                  title={doc.title}
                  description={
                    <Space direction="vertical" size={2}>
                      <Typography.Text type="secondary">
                        来源：{doc.source_name ?? doc.source_type} · 切片：{doc.chunk_count}
                      </Typography.Text>
                      {doc.error_message ? (
                        <Typography.Text type="danger">{doc.error_message}</Typography.Text>
                      ) : null}
                    </Space>
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
