import { Button, Card, Select, Space, Table, Tag, message } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";
import { Optimization as Opt } from "../api/types";

const statusColor: Record<string, string> = { PENDING: "blue", ADOPTED: "green", REJECTED: "default" };

export default function Optimization() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | null>(null);
  const [rows, setRows] = useState<Opt[]>([]);

  useEffect(() => {
    if (units.length && unitId === null) setUnitId(units[0].id);
  }, [units, unitId]);

  const load = (id: number) => api.get<Opt[]>(`/optimization?unit_id=${id}`).then((r) => setRows(r.data));

  useEffect(() => {
    if (unitId !== null) load(unitId);
  }, [unitId]);

  const generate = async () => {
    if (unitId === null) return;
    try {
      await api.post("/optimization/generate", { unit_id: unitId });
      await load(unitId);
      message.success("已生成 AI 燃烧优化建议");
    } catch {
      message.error("生成失败：该机组暂无工况数据");
    }
  };

  const setStatus = async (id: number, status: string) => {
    await api.patch(`/optimization/${id}`, { status });
    if (unitId !== null) load(unitId);
  };

  const columns = [
    { title: "编号", dataIndex: "code" },
    { title: "时间", dataIndex: "ts", render: (v: string) => dayjs(v).format("MM-DD HH:mm") },
    { title: "负荷(MW)", dataIndex: "load_mw" },
    { title: "当前氧量(%)", dataIndex: "current_o2" },
    {
      title: "建议氧量(%)",
      dataIndex: "recommended_o2",
      render: (v: number, r: Opt) => <span style={{ color: v < r.current_o2 ? "#0e7490" : undefined }}>{v}</span>,
    },
    { title: "预期降煤耗(g/kWh)", dataIndex: "predicted_coal_rate_drop", render: (v: number) => <b style={{ color: "#389e0d" }}>{v}</b> },
    { title: "折合日省(元)", dataIndex: "predicted_saving_yuan_day" },
    { title: "置信度", dataIndex: "confidence", render: (v: number) => `${Math.round(v * 100)}%` },
    { title: "状态", dataIndex: "status", render: (v: string) => <Tag color={statusColor[v]}>{v}</Tag> },
    {
      title: "操作",
      render: (_: unknown, r: Opt) =>
        r.status === "PENDING" ? (
          <Space>
            <Button size="small" type="link" onClick={() => setStatus(r.id, "ADOPTED")}>采纳</Button>
            <Button size="small" type="link" danger onClick={() => setStatus(r.id, "REJECTED")}>驳回</Button>
          </Space>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="AI 燃烧优化建议"
        extra={
          <span>
            <Select
              style={{ width: 220, marginRight: 8 }}
              value={unitId ?? undefined}
              onChange={setUnitId}
              options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
            />
            <Button type="primary" onClick={generate}>生成建议</Button>
          </span>
        }
      >
        <Table
          rowKey="id"
          dataSource={rows}
          columns={columns}
          size="small"
          pagination={false}
          expandable={{
            expandedRowRender: (r) => (
              <div style={{ lineHeight: 1.9 }}>
                <div><b>寻优依据：</b>{r.rationale}（模型 {r.model_version}）</div>
                <div><b>配风建议：</b>{r.recommended_secondary_air}</div>
                <div><b>磨煤机组合：</b>{r.recommended_mill_combo}</div>
              </div>
            ),
          }}
        />
      </Card>
    </div>
  );
}
