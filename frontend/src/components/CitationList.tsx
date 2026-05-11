import { List, Typography } from "antd";

type Citation = {
  chunk_id: string;
  snippet: string;
  source_type: string;
  source_title?: string | null;
};

export function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <List
      dataSource={citations}
      locale={{ emptyText: "暂无引用片段" }}
      renderItem={(item) => (
        <List.Item>
          <div>
            <Typography.Text strong>{item.source_title || item.source_type}</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              {item.snippet}
            </Typography.Paragraph>
          </div>
        </List.Item>
      )}
    />
  );
}
