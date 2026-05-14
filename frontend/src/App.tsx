import {
  ApiOutlined,
  BookOutlined,
  BranchesOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Badge, Layout, Menu, Select, Space, Tag, Typography } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useCurrentProject } from "./hooks/useCurrentProject";

const items = [
  { key: "/", icon: <DashboardOutlined />, label: "项目总览" },
  { key: "/review", icon: <SafetyCertificateOutlined />, label: "代码审查" },
  { key: "/testgen", icon: <ExperimentOutlined />, label: "测试生成" },
  { key: "/chat", icon: <MessageOutlined />, label: "知识问答" },
  { key: "/github", icon: <BranchesOutlined />, label: "GitHub 集成" },
  { key: "/kb", icon: <BookOutlined />, label: "知识库" },
  { key: "/models", icon: <ApiOutlined />, label: "模型配置" },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projects, projectId, setProjectId, currentProject, isLoading } = useCurrentProject();

  return (
    <Layout className="app-shell">
      <Layout.Sider width={248} theme="light" className="shell-sider">
        <div className="brand-block">
          <div className="brand-title">Lab AI Reviewer</div>
          <div className="brand-subtitle">实验室研发流程中的 AI 审查、测试与知识平台</div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={({ key }) => navigate(key)}
          style={{ borderInlineEnd: "none" }}
        />
      </Layout.Sider>
      <Layout className="shell-main">
        <Layout.Header className="app-header">
          <div>
            <Typography.Text strong>
              {currentProject?.name ?? "加载项目中"}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
              {currentProject?.description ?? "默认演示项目"}
            </Typography.Text>
          </div>
          <div className="header-meta">
            <Select
              loading={isLoading}
              value={projectId || undefined}
              style={{ width: 220 }}
              options={projects.map((project) => ({
                value: project.id,
                label: project.name,
              }))}
              onChange={setProjectId}
            />
            <Space size="middle">
              <Badge status="processing" text="模型在线" />
              <Badge status="success" text="GitHub 已连接" />
              <Tag color="blue">异步任务模式</Tag>
            </Space>
          </div>
        </Layout.Header>
        <Layout.Content className="app-content">
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
