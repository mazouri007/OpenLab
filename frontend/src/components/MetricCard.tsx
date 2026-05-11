import { Card, Statistic } from "antd";

export function MetricCard({
  title,
  value,
  suffix,
}: {
  title: string;
  value: number;
  suffix?: string;
}) {
  return (
    <Card className="metric-card">
      <Statistic title={title} value={value} suffix={suffix} />
    </Card>
  );
}

