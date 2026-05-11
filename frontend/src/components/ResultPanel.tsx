import { Card } from "antd";
import type { PropsWithChildren } from "react";

type Props = PropsWithChildren<{
  title: string;
}>;

export function ResultPanel({ title, children }: Props) {
  return (
    <Card title={title} className="result-panel">
      {children}
    </Card>
  );
}

