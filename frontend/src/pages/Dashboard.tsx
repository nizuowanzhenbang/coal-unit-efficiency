import { Col, Empty, Row, Spin, Tag } from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { DashboardOverview } from "../api/types";

const statusColor: Record<string, string> = {
  GOOD: "#38e1c4",
  WATCH: "#fadb14",
  BAD: "#ff7875",
  NO_DATA: "#8c8c8c",
};

function Kpi({ value, title, suffix }: { value: number | string; title: string; suffix?: string }) {
  return (
    <div className="dash-kpi">
      <div className="v">
        {value}
        {suffix ? <span style={{ fontSize: 14 }}> {suffix}</span> : null}
      </div>
      <div className="t">{title}</div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () =>
      api.get<DashboardOverview>("/dashboard/overview").then((r) => setData(r.data)).finally(() => setLoading(false));
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  if (loading) return <div className="dash-screen"><Spin /></div>;
  if (!data) return <div className="dash-screen"><Empty /></div>;

  const f = data.fleet;
  const cards = data.units;

  const barOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { textStyle: { color: "#cfe" }, data: ["实际供电煤耗", "设计目标"] },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: { type: "category", data: cards.map((c) => c.code), axisLabel: { color: "#cfe" } },
    yAxis: { type: "value", name: "g/kWh", min: 270, axisLabel: { color: "#cfe" }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } } },
    series: [
      { name: "实际供电煤耗", type: "bar", data: cards.map((c) => c.net_coal_rate ?? null), itemStyle: { color: "#38e1c4" } },
      { name: "设计目标", type: "line", data: cards.map((c) => c.design_net_coal_rate ?? null), itemStyle: { color: "#fadb14" } },
    ],
  };

  const gauge = (c: (typeof cards)[number]) => ({
    backgroundColor: "transparent",
    series: [
      {
        type: "gauge",
        min: 270,
        max: 340,
        radius: "92%",
        progress: { show: true, width: 10 },
        axisLine: { lineStyle: { width: 10 } },
        axisLabel: { color: "#9fd3e3", fontSize: 9, distance: 12 },
        pointer: { width: 4 },
        detail: {
          valueAnimation: true,
          formatter: c.net_coal_rate ? `{value} g/kWh` : "无数据",
          color: statusColor[c.status],
          fontSize: 16,
          offsetCenter: [0, "70%"],
        },
        data: [{ value: c.net_coal_rate ?? 0 }],
        title: { show: false },
      },
    ],
  });

  return (
    <div className="dash-screen">
      <Row gutter={[12, 12]}>
        <Col xs={12} md={6}><Kpi value={f.unit_count} title="在运机组" suffix="台" /></Col>
        <Col xs={12} md={6}><Kpi value={f.total_load_mw} title="机组群总负荷" suffix="MW" /></Col>
        <Col xs={12} md={6}><Kpi value={f.avg_net_coal_rate} title="平均供电煤耗" suffix="g/kWh" /></Col>
        <Col xs={12} md={6}><Kpi value={f.adopted_saving_yuan_day} title="已采纳建议日省" suffix="元/日" /></Col>
        <Col xs={12} md={6}><Kpi value={f.open_alerts} title="未关闭预警" suffix="条" /></Col>
        <Col xs={12} md={6}><Kpi value={f.critical_alerts} title="严重预警" suffix="条" /></Col>
        <Col xs={12} md={6}><Kpi value={f.pending_optimizations} title="待处理优化建议" suffix="条" /></Col>
      </Row>

      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        {cards.map((c) => (
          <Col xs={24} md={8} key={c.unit_id}>
            <div className="dash-kpi">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <b style={{ color: "#e6f7ff" }}>{c.code} · {c.name}</b>
                <Tag color={statusColor[c.status]}>{c.status}</Tag>
              </div>
              <ReactECharts option={gauge(c)} style={{ height: 180 }} />
              <div style={{ fontSize: 12, color: "#9fd3e3" }}>
                负荷 {c.load_mw ?? "-"} MW · 锅炉效率 {c.boiler_eff ?? "-"}% · 厂用电率 {c.aux_ratio ?? "-"}%
                {c.deviation != null && (
                  <span style={{ color: c.deviation > 0 ? "#ff7875" : "#38e1c4" }}>
                    {" "}· 较设计 {c.deviation > 0 ? "+" : ""}{c.deviation} g/kWh
                  </span>
                )}
              </div>
            </div>
          </Col>
        ))}
      </Row>

      <Row style={{ marginTop: 12 }}>
        <Col span={24}>
          <div className="dash-kpi">
            <div className="t" style={{ marginBottom: 8 }}>各机组供电煤耗 vs 设计目标</div>
            <ReactECharts option={barOption} style={{ height: 280 }} />
          </div>
        </Col>
      </Row>
    </div>
  );
}
