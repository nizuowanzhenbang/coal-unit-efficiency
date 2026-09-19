import { Alert, Button, Card, Descriptions, Select, Space, Switch, Table, Tag, Typography, message } from "antd";
import { isAxiosError } from "axios";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";
import { Optimization as Opt } from "../api/types";

const statusColor: Record<string, string> = { PENDING: "blue", ADOPTED: "green", REJECTED: "default" };
const reasonLabel: Record<string, string> = {
  NO_HISTORY: "未使用历史样本", HISTORY_DISABLED: "已选择经验规则", INSUFFICIENT_HISTORY: "有效历史不足24条",
  RANK_DEFICIENT: "样本缺少独立变化，无法可靠拟合", FIT_FAILED: "模型计算未通过检查",
  VALIDATION_FAILED: "留出验证未达到误差或基线要求", VALIDATED: "已通过留出验证",
  OUTSIDE_TRAINING_RANGE: "当前工况或建议氧量超出训练范围",
};

export default function Optimization() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | null>(null);
  const [rows, setRows] = useState<Opt[]>([]);
  const [useHistory, setUseHistory] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (units.length && unitId === null) setUnitId(units[0].id);
  }, [units, unitId]);

  const load = (id: number) => api.get<Opt[]>(`/optimization?unit_id=${id}`).then((r) => setRows(r.data));

  useEffect(() => {
    if (unitId !== null) load(unitId);
  }, [unitId]);

  const generate = async () => {
    if (unitId === null) return;
    setGenerating(true);
    try {
      await api.post("/optimization/generate", { unit_id: unitId, use_history: useHistory });
      await load(unitId);
      message.success("已生成建议及评估依据");
    } catch (error) {
      message.error(isAxiosError(error) ? error.response?.data?.detail || "生成失败" : "生成失败");
    } finally {
      setGenerating(false);
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
    { title: "建议依据", render: (_: unknown, r: Opt) => <Tag color={r.evaluation?.mode === "REGRESSION" ? "green" : "orange"}>
      {r.evaluation?.mode === "REGRESSION" ? "验证模型" : r.evaluation ? "经验规则" : "旧记录：未评估"}</Tag> },
    { title: "验证评分（非概率）", dataIndex: "confidence", render: (v: number, r: Opt) => r.evaluation?.mode === "REGRESSION" ? v.toFixed(2) : "未验证" },
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
        title="燃烧优化建议与模型评估"
        extra={
          <span>
            <Select
              style={{ width: 220, marginRight: 8 }}
              value={unitId ?? undefined}
              onChange={setUnitId}
              options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
            />
            <Space><Switch checked={useHistory} onChange={setUseHistory} checkedChildren="使用历史" unCheckedChildren="经验规则" />
            <Button type="primary" onClick={generate} loading={generating}>生成建议</Button></Space>
          </span>
        }
      >
        <Alert type="info" showIcon style={{ marginBottom: 16 }} message="历史模型需先通过按时间留出的样本验证；不足或越界时自动使用经验规则。"
          description="误差以 g/kWh 表示，评分不是成功概率。氧量目标和飞灰修正含经验假设，预期节煤与金额均为估算；采纳记录不代表已实现收益。" />
        <Table
          rowKey="id"
          dataSource={rows}
          columns={columns}
          size="small"
          pagination={false}
          expandable={{
            expandedRowRender: (r) => (
              <div style={{ lineHeight: 1.9 }}>
                {r.evaluation && <Descriptions size="small" bordered column={3} style={{ marginBottom: 12 }}>
                  <Descriptions.Item label="评估结果">{reasonLabel[r.evaluation.reason] || r.evaluation.reason}</Descriptions.Item>
                  <Descriptions.Item label="有效/排除样本">{r.evaluation.valid_samples} / {r.evaluation.rejected_samples}</Descriptions.Item>
                  <Descriptions.Item label="训练/验证样本">{r.evaluation.train_samples} / {r.evaluation.validation_samples}</Descriptions.Item>
                  <Descriptions.Item label="验证 MAE (g/kWh)">{r.evaluation.validation_mae?.toFixed(3) ?? "无"}</Descriptions.Item>
                  <Descriptions.Item label="均值基线 MAE (g/kWh)">{r.evaluation.baseline_mae?.toFixed(3) ?? "无"}</Descriptions.Item>
                  <Descriptions.Item label="来源工况 ID">{r.evaluation.snapshot_id ?? "无"}</Descriptions.Item>
                  <Descriptions.Item label="计算时容量 (MW)">{r.evaluation.input_snapshot?.capacity_mw ?? "无"}</Descriptions.Item>
                  <Descriptions.Item label="计算时标煤价 (元/吨)">{r.evaluation.input_snapshot?.standard_coal_price ?? "无"}</Descriptions.Item>
                  <Descriptions.Item label="输入指纹"><Typography.Text copyable={!!r.evaluation.input_sha256}>{r.evaluation.input_sha256 || "无"}</Typography.Text></Descriptions.Item>
                  <Descriptions.Item label="历史时间范围" span={3}>{r.evaluation.history_start || "无"} ～ {r.evaluation.history_end || "无"}</Descriptions.Item>
                  <Descriptions.Item label="数据指纹" span={3}><Typography.Text copyable={!!r.evaluation.dataset_sha256}>
                    {r.evaluation.dataset_sha256 || "未使用历史数据"}</Typography.Text></Descriptions.Item>
                </Descriptions>}
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
