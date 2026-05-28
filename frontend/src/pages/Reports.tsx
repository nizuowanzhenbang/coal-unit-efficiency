import { Button, Card, Select, Table, Tag, message } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";
import { EnergyReport } from "../api/types";

export default function Reports() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | null>(null);
  const [rows, setRows] = useState<EnergyReport[]>([]);

  useEffect(() => {
    if (units.length && unitId === null) setUnitId(units[0].id);
  }, [units, unitId]);

  const load = (id: number) => api.get<EnergyReport[]>(`/reports?unit_id=${id}`).then((r) => setRows(r.data));

  useEffect(() => {
    if (unitId !== null) load(unitId);
  }, [unitId]);

  const generate = async () => {
    if (unitId === null) return;
    const end = dayjs();
    const start = end.subtract(1, "day");
    await api.post("/reports/generate", {
      unit_id: unitId,
      period_type: "DAILY",
      period_start: start.toISOString(),
      period_end: end.toISOString(),
    });
    load(unitId);
    message.success("已生成能效日报");
  };

  const issue = async (id: number) => {
    await api.post(`/reports/${id}/issue`);
    if (unitId !== null) load(unitId);
  };

  const columns = [
    { title: "编号", dataIndex: "code" },
    { title: "类型", dataIndex: "period_type" },
    { title: "平均供电煤耗", dataIndex: "avg_net_coal_rate" },
    { title: "目标", dataIndex: "target_net_coal_rate" },
    {
      title: "偏差",
      dataIndex: "coal_rate_deviation",
      render: (v: number) => <span style={{ color: v > 0 ? "#cf1322" : "#389e0d" }}>{v > 0 ? "+" : ""}{v}</span>,
    },
    { title: "节标煤(t)", dataIndex: "coal_saving_t" },
    { title: "节约金额(元)", dataIndex: "cost_saving_yuan" },
    { title: "减碳(t)", dataIndex: "co2_reduction_t" },
    { title: "状态", dataIndex: "status", render: (v: string) => <Tag color={v === "ISSUED" ? "green" : "blue"}>{v}</Tag> },
    {
      title: "操作",
      render: (_: unknown, r: EnergyReport) =>
        r.status === "DRAFT" ? <Button size="small" type="link" onClick={() => issue(r.id)}>签发</Button> : null,
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="能效报告"
        extra={
          <span>
            <Select
              style={{ width: 220, marginRight: 8 }}
              value={unitId ?? undefined}
              onChange={setUnitId}
              options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
            />
            <Button type="primary" onClick={generate}>生成日报</Button>
          </span>
        }
      >
        <Table
          rowKey="id"
          dataSource={rows}
          columns={columns}
          size="small"
          pagination={false}
          expandable={{ expandedRowRender: (r) => <div style={{ lineHeight: 1.8 }}>{r.summary}</div> }}
        />
      </Card>
    </div>
  );
}
