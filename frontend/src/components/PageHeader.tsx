import { Space, Typography } from "antd";
import type { PropsWithChildren, ReactNode } from "react";

type Props = PropsWithChildren<{
  title: string;
  description?: string;
  extra?: ReactNode;
}>;

export function PageHeader({ title, description, extra, children }: Props) {
  return (
    <div className="page-header">
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          {title}
        </Typography.Title>
        {description ? (
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {description}
          </Typography.Paragraph>
        ) : null}
      </div>
      <Space>{children ?? extra}</Space>
    </div>
  );
}

