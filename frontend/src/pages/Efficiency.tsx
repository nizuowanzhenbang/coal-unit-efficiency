import { Card, Col, Row, Select, Statistic } from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";
import { EfficiencyRecord } from "../api/types";

interface Trend {
  ts: string[];
  net_coal_rate: number[];
  gross_coal_rate: number[];
  boiler_eff: number[];
  heat_rate: number[];
  load_mw: number[];
}

export default function Efficiency() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | null>(null);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [latest, setLatest] = useState<EfficiencyRecord | null>(null);

  useEffect(() => {
    if (units.length && unitId === null) setUnitId(units[0].id);
  }, [units, unitId]);

  useEffect(() => {
    if (unitId === null) return;
    api.get<Trend>(`/efficiency/trend/${unitId}`).then((r) => setTrend(r.data));
    api.get<EfficiencyRecord[]>(`/efficiency?unit_id=${unitId}&limit=1`).then((r) => setLatest(r.data[0] ?? null));
  }, [unitId]);

  const trendOption = {
    tooltip: { trigger: "axis" },
    legend: { data: ["供电煤耗", "锅炉效率"] },
    grid: { left: 50, right: 50, top: 40, bottom: 30 },
    xAxis: { type: "category", data: trend?.ts.map((t) => t.slice(11, 16)) ?? [] },
    yAxis: [
      { type: "value", name: "g/kWh", min: "dataMin" },
      { type: "value", name: "%", min: "dataMin" },
    ],
    series: [
      { name: "供电煤耗", type: "line", smooth: true, data: trend?.net_coal_rate ?? [], itemStyle: { color: "#0e7490" } },
      { name: "锅炉效率", type: "line", smooth: true, yAxisIndex: 1, data: trend?.boiler_eff ?? [], itemStyle: { color: "#52c41a" } },
    ],
  };

  const lossOption = latest && {
    tooltip: { trigger: "item", formatter: "{b}: {c}% ({d}%)" },
    legend: { bottom: 0 },
    series: [
      {
        type: "pie",
        radius: ["40%", "70%"],
        data: [
          { name: "排烟热损失 q2", value: latest.q2 },
          { name: "化学不完全 q3", value: latest.q3 },
          { name: "机械不完全 q4", value: latest.q4 },
          { name: "散热损失 q5", value: latest.q5 },
          { name: "灰渣物理热 q6", value: latest.q6 },
        ],
      },
    ],
  };

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="能效指标分析"
        extra={
          <Select
            style={{ width: 240 }}
            value={unitId ?? undefined}
            onChange={setUnitId}
            options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
          />
        }
      >
        {latest && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={4}><Statistic title="供电煤耗(g/kWh)" value={latest.net_coal_rate} precision={2} /></Col>
            <Col span={4}><Statistic title="发电煤耗(g/kWh)" value={latest.gross_coal_rate} precision={2} /></Col>
            <Col span={4}><Statistic title="锅炉效率(%)" value={latest.boiler_eff} precision={2} /></Col>
            <Col span={4}><Statistic title="热耗率(kJ/kWh)" value={latest.heat_rate} precision={0} /></Col>
            <Col span={4}><Statistic title="厂用电率(%)" value={latest.aux_ratio} precision={2} /></Col>
            <Col span={4}><Statistic title="过量空气系数" value={latest.excess_air} precision={3} /></Col>
          </Row>
        )}
        <Row gutter={16}>
          <Col xs={24} md={16}>
            <ReactECharts option={trendOption} style={{ height: 320 }} />
          </Col>
          <Col xs={24} md={8}>
            {lossOption && <ReactECharts option={lossOption} style={{ height: 320 }} />}
          </Col>
        </Row>
      </Card>
    </div>
  );
}
