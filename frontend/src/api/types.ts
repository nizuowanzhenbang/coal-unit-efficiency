export interface Unit {
  id: number;
  code: string;
  name: string;
  capacity_mw: number;
  boiler_model: string;
  turbine_model: string;
  design_net_coal_rate: number;
  design_boiler_eff: number;
  design_pipe_eff: number;
  design_turbine_eff: number;
  design_heat_rate: number;
  design_aux_ratio: number;
  design_ash_ar: number;
  design_coal_lhv: number;
  commission_date: string | null;
  is_active: boolean;
}

export interface EfficiencyRecord {
  id: number;
  unit_id: number;
  ts: string;
  load_mw: number;
  gross_coal_rate: number;
  net_coal_rate: number;
  boiler_eff: number;
  pipe_eff: number;
  turbine_eff: number;
  gross_eff: number;
  net_eff: number;
  heat_rate: number;
  aux_ratio: number;
  excess_air: number;
  q2: number;
  q3: number;
  q4: number;
  q5: number;
  q6: number;
}

export interface Deviation {
  id: number;
  unit_id: number;
  ts: string;
  indicator: string;
  label: string;
  actual_value: number;
  target_value: number;
  deviation: number;
  coal_rate_impact: number;
  severity: string;
}

export interface Optimization {
  id: number;
  unit_id: number;
  code: string;
  ts: string;
  load_mw: number;
  current_o2: number;
  recommended_o2: number;
  current_flue_temp: number;
  current_fly_ash_carbon: number;
  recommended_secondary_air: string;
  recommended_mill_combo: string;
  predicted_coal_rate_drop: number;
  predicted_saving_yuan_day: number;
  confidence: number;
  model_version: string;
  rationale: string;
  status: string;
}

export interface EnergyReport {
  id: number;
  unit_id: number;
  code: string;
  period_type: string;
  period_start: string;
  period_end: string;
  avg_net_coal_rate: number;
  target_net_coal_rate: number;
  coal_rate_deviation: number;
  avg_boiler_eff: number;
  avg_heat_rate: number;
  avg_aux_ratio: number;
  total_gen_mwh: number;
  coal_saving_t: number;
  cost_saving_yuan: number;
  co2_reduction_t: number;
  top_deviations: string;
  summary: string;
  status: string;
  created_at: string;
}

export interface Alert {
  id: number;
  unit_id: number;
  code: string;
  category: string;
  level: string;
  title: string;
  measured_value: number;
  threshold_value: number;
  message: string;
  status: string;
  triggered_at: string;
  closed_at: string | null;
}

export interface DashboardUnitCard {
  unit_id: number;
  code: string;
  name: string;
  capacity_mw: number;
  load_mw?: number;
  net_coal_rate?: number;
  design_net_coal_rate?: number;
  deviation?: number;
  boiler_eff?: number;
  heat_rate?: number;
  aux_ratio?: number;
  ts?: string;
  status: string;
}

export interface DashboardOverview {
  fleet: {
    unit_count: number;
    total_load_mw: number;
    avg_net_coal_rate: number;
    open_alerts: number;
    critical_alerts: number;
    pending_optimizations: number;
    adopted_saving_yuan_day: number;
  };
  units: DashboardUnitCard[];
}
