import { Card } from "antd";
import type { PropsWithChildren } from "react";

type Props = PropsWithChildren<{
  title: string;
}>;

export function SectionCard({ title, children }: Props) {
  return <Card title={title}>{children}</Card>;
}

