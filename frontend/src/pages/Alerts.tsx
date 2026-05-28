import { Button, Card, Select, Space, Table, Tag } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";
import { Alert } from "../api/types";

const levelColor: Record<string, string> = { INFO: "blue", WARNING: "gold", CRITICAL: "red" };
const statusColor: Record<string, string> = { OPEN: "red", ACKED: "gold", CLOSED: "green" };
const categoryLabel: Record<string, string> = {
  COAL_RATE: "供电煤耗",
  BOILER_EFF: "锅炉效率",
  DEVIATION: "运行耗差",
};

export default function Alerts() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | undefined>(undefined);
  const [rows, setRows] = useState<Alert[]>([]);

  const load = () => {
    const q = unitId ? `?unit_id=${unitId}` : "";
    api.get<Alert[]>(`/alerts${q}`).then((r) => setRows(r.data));
  };

  useEffect(load, [unitId]);

  const setStatus = async (id: number, status: string) => {
    await api.patch(`/alerts/${id}`, { status });
    load();
  };

  const columns = [
    { title: "编号", dataIndex: "code" },
    { title: "类别", dataIndex: "category", render: (v: string) => categoryLabel[v] ?? v },
    { title: "级别", dataIndex: "level", render: (v: string) => <Tag color={levelColor[v]}>{v}</Tag> },
    { title: "标题", dataIndex: "title" },
    { title: "实测值", dataIndex: "measured_value" },
    { title: "阈值", dataIndex: "threshold_value" },
    { title: "触发时间", dataIndex: "triggered_at", render: (v: string) => dayjs(v).format("MM-DD HH:mm") },
    { title: "状态", dataIndex: "status", render: (v: string) => <Tag color={statusColor[v]}>{v}</Tag> },
    {
      title: "操作",
      render: (_: unknown, r: Alert) =>
        r.status !== "CLOSED" ? (
          <Space>
            {r.status === "OPEN" && <Button size="small" type="link" onClick={() => setStatus(r.id, "ACKED")}>确认</Button>}
            <Button size="small" type="link" onClick={() => setStatus(r.id, "CLOSED")}>关闭</Button>
          </Space>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="能效预警中心"
        extra={
          <Select
            allowClear
            placeholder="全部机组"
            style={{ width: 220 }}
            value={unitId}
            onChange={setUnitId}
            options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
          />
        }
      >
        <Table
          rowKey="id"
          dataSource={rows}
          columns={columns}
          size="small"
          pagination={{ pageSize: 20 }}
          expandable={{ expandedRowRender: (r) => <div>{r.message}</div> }}
        />
      </Card>
    </div>
  );
}
