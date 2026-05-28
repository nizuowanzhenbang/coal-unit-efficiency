import { Card, Select, Table } from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useUnits } from "../api/hooks";

interface Snapshot {
  id: number;
  ts: string;
  load_mw: number;
  flue_gas_temp: number;
  flue_o2: number;
  fly_ash_carbon: number;
  condenser_vacuum: number;
  main_steam_temp: number;
  reheat_steam_temp: number;
  coal_flow_tph: number;
  coal_lhv: number;
  aux_power_mw: number;
}

export default function Snapshots() {
  const units = useUnits();
  const [unitId, setUnitId] = useState<number | null>(null);
  const [rows, setRows] = useState<Snapshot[]>([]);

  useEffect(() => {
    if (units.length && unitId === null) setUnitId(units[0].id);
  }, [units, unitId]);

  useEffect(() => {
    if (unitId === null) return;
    api.get<Snapshot[]>(`/snapshots?unit_id=${unitId}&limit=100`).then((r) => setRows(r.data));
  }, [unitId]);

  const columns = [
    { title: "时间", dataIndex: "ts", render: (v: string) => dayjs(v).format("MM-DD HH:mm") },
    { title: "负荷(MW)", dataIndex: "load_mw" },
    { title: "主汽温(℃)", dataIndex: "main_steam_temp" },
    { title: "再热汽温(℃)", dataIndex: "reheat_steam_temp" },
    { title: "排烟温度(℃)", dataIndex: "flue_gas_temp" },
    { title: "含氧量(%)", dataIndex: "flue_o2" },
    { title: "飞灰含碳(%)", dataIndex: "fly_ash_carbon" },
    { title: "真空(kPa)", dataIndex: "condenser_vacuum" },
    { title: "煤量(t/h)", dataIndex: "coal_flow_tph" },
    { title: "入炉热值(kJ/kg)", dataIndex: "coal_lhv" },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="运行工况监测"
        extra={
          <Select
            style={{ width: 240 }}
            value={unitId ?? undefined}
            onChange={setUnitId}
            options={units.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))}
          />
        }
      >
        <Table rowKey="id" dataSource={rows} columns={columns} size="small" pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
}
