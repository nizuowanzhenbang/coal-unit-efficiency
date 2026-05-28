import { Card, Descriptions, Table, Tag } from "antd";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Unit } from "../api/types";

export default function Units() {
  const [units, setUnits] = useState<Unit[]>([]);

  useEffect(() => {
    api.get<Unit[]>("/units").then((r) => setUnits(r.data));
  }, []);

  const columns = [
    { title: "机组编号", dataIndex: "code" },
    { title: "名称", dataIndex: "name" },
    { title: "容量(MW)", dataIndex: "capacity_mw" },
    { title: "锅炉型号", dataIndex: "boiler_model" },
    { title: "设计供电煤耗(g/kWh)", dataIndex: "design_net_coal_rate" },
    { title: "设计锅炉效率(%)", dataIndex: "design_boiler_eff" },
    { title: "设计厂用电率(%)", dataIndex: "design_aux_ratio" },
    {
      title: "状态",
      dataIndex: "is_active",
      render: (v: boolean) => <Tag color={v ? "green" : "default"}>{v ? "在运" : "停运"}</Tag>,
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card title="机组台账">
        <Table
          rowKey="id"
          dataSource={units}
          columns={columns}
          pagination={false}
          expandable={{
            expandedRowRender: (u) => (
              <Descriptions size="small" column={3} bordered>
                <Descriptions.Item label="汽机型号">{u.turbine_model}</Descriptions.Item>
                <Descriptions.Item label="设计热耗(kJ/kWh)">{u.design_heat_rate}</Descriptions.Item>
                <Descriptions.Item label="设计汽机效率(%)">{u.design_turbine_eff}</Descriptions.Item>
                <Descriptions.Item label="设计收到基灰分(%)">{u.design_ash_ar}</Descriptions.Item>
                <Descriptions.Item label="设计入炉煤热值(kJ/kg)">{u.design_coal_lhv}</Descriptions.Item>
                <Descriptions.Item label="投产日期">{u.commission_date ?? "-"}</Descriptions.Item>
              </Descriptions>
            ),
          }}
        />
      </Card>
    </div>
  );
}
