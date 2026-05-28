import { Button, Card, Select, Table, Tag, message } from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";
import { Deviation as Dev } from "../api/types";

const sevColor: Record<string, string> = { NORMAL: "green", WATCH: "gold", ALERT: "red" };

export default function Deviation() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | null>(null);
  const [rows, setRows] = useState<Dev[]>([]);

  useEffect(() => {
    if (units.length && unitId === null) setUnitId(units[0].id);
  }, [units, unitId]);

  const load = (id: number) => api.get<Dev[]>(`/deviations?unit_id=${id}&limit=20`).then((r) => setRows(r.data));

  useEffect(() => {
    if (unitId !== null) load(unitId);
  }, [unitId]);

  const analyze = async () => {
    if (unitId === null) return;
    try {
      await api.post(`/deviations/analyze/${unitId}`);
      await load(unitId);
      message.success("已基于最新工况重新分析");
    } catch {
      message.error("分析失败：该机组暂无工况数据");
    }
  };

  // 取每个指标最新一条做瀑布图
  const latestByIndicator = Object.values(
    rows.reduce<Record<string, Dev>>((acc, d) => {
      if (!acc[d.indicator]) acc[d.indicator] = d;
      return acc;
    }, {})
  );

  const waterfall = {
    tooltip: { trigger: "axis" },
    grid: { left: 60, right: 20, top: 30, bottom: 40 },
    xAxis: { type: "category", data: latestByIndicator.map((d) => d.label) },
    yAxis: { type: "value", name: "g/kWh" },
    series: [
      {
        type: "bar",
        data: latestByIndicator.map((d) => ({
          value: d.coal_rate_impact,
          itemStyle: { color: d.coal_rate_impact > 0 ? "#ff7875" : "#52c41a" },
        })),
        label: { show: true, position: "top", formatter: "{c}" },
      },
    ],
  };

  const columns = [
    { title: "指标", dataIndex: "label" },
    { title: "实际值", dataIndex: "actual_value" },
    { title: "目标值", dataIndex: "target_value" },
    { title: "偏差", dataIndex: "deviation" },
    {
      title: "折算煤耗影响(g/kWh)",
      dataIndex: "coal_rate_impact",
      render: (v: number) => <span style={{ color: v > 0 ? "#cf1322" : "#389e0d" }}>{v > 0 ? "+" : ""}{v}</span>,
    },
    { title: "等级", dataIndex: "severity", render: (v: string) => <Tag color={sevColor[v]}>{v}</Tag> },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="耗差分析（小指标 → 折算供电煤耗）"
        extra={
          <span>
            <Select
              style={{ width: 220, marginRight: 8 }}
              value={unitId ?? undefined}
              onChange={setUnitId}
              options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
            />
            <Button type="primary" onClick={analyze}>基于最新工况分析</Button>
          </span>
        }
      >
        {latestByIndicator.length > 0 && <ReactECharts option={waterfall} style={{ height: 280 }} />}
        <Table rowKey="id" dataSource={latestByIndicator} columns={columns} pagination={false} size="small" style={{ marginTop: 16 }} />
      </Card>
    </div>
  );
}
