import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

type Props<T extends { id: string }> = {
  columns: ColumnsType<T>;
  dataSource: T[];
  loading?: boolean;
  onRowClick?: (record: T) => void;
};

export function TaskTable<T extends { id: string }>({
  columns,
  dataSource,
  loading,
  onRowClick,
}: Props<T>) {
  return (
    <Table<T>
      rowKey="id"
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      pagination={{ pageSize: 8 }}
      onRow={(record) => ({
        onClick: () => onRowClick?.(record),
      })}
    />
  );
}

