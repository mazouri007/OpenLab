import { Tag } from "antd";

const COLOR_MAP: Record<string, string> = {
  pending: "default",
  queued: "processing",
  running: "blue",
  completed: "success",
  failed: "error",
  critical: "error",
  high: "volcano",
  medium: "gold",
  low: "green",
  info: "default",
};

export function StatusTag({ value }: { value: string }) {
  return <Tag color={COLOR_MAP[value] ?? "default"}>{value}</Tag>;
}

