import {
  AlertOutlined,
  BulbOutlined,
  DashboardOutlined,
  DotChartOutlined,
  FileTextOutlined,
  FundOutlined,
  LineChartOutlined,
  LogoutOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Layout, Menu, Tag } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth";

const { Header, Sider, Content } = Layout;

const items = [
  { key: "/", icon: <DashboardOutlined />, label: "能效驾驶舱" },
  { key: "/units", icon: <ThunderboltOutlined />, label: "机组台账" },
  { key: "/snapshots", icon: <FundOutlined />, label: "运行工况" },
  { key: "/efficiency", icon: <LineChartOutlined />, label: "能效指标" },
  { key: "/deviation", icon: <DotChartOutlined />, label: "耗差分析" },
  { key: "/optimization", icon: <BulbOutlined />, label: "AI燃烧优化" },
  { key: "/reports", icon: <FileTextOutlined />, label: "能效报告" },
  { key: "/alerts", icon: <AlertOutlined />, label: "能效预警" },
];

const roleLabels: Record<string, string> = {
  ADMIN: "管理员",
  OPERATOR: "运行值班",
  ENERGY_ENG: "能效专工",
  MANAGER: "生产管理",
  VIEWER: "访客",
};

export default function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const { role, fullName, logout } = useAuth();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="dark" breakpoint="lg" collapsedWidth="0">
        <div style={{ color: "#38e1c4", padding: "18px 16px", fontWeight: 700, fontSize: 15 }}>
          ⚡ 机组能效优化
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[loc.pathname]}
          items={items}
          onClick={(e) => nav(e.key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: "#fff", display: "flex", justifyContent: "space-between", alignItems: "center", paddingInline: 20 }}>
          <span style={{ fontWeight: 600 }}>燃煤机组能效与智能燃烧优化系统</span>
          <span>
            <Tag color="cyan">{roleLabels[role ?? ""] ?? role}</Tag>
            <span style={{ marginRight: 12 }}>{fullName}</span>
            <Button size="small" icon={<LogoutOutlined />} onClick={() => { logout(); nav("/login"); }}>
              退出
            </Button>
          </span>
        </Header>
        <Content style={{ margin: 0 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
