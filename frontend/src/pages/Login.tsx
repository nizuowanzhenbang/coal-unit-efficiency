import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../store/auth";

const { Title, Paragraph, Text } = Typography;

export default function Login() {
  const nav = useNavigate();
  const setAuth = useAuth((s) => s.setAuth);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onFinish = async (v: { username: string; password: string }) => {
    setLoading(true);
    setError(null);
    try {
      const form = new URLSearchParams();
      form.set("username", v.username);
      form.set("password", v.password);
      const { data } = await api.post("/auth/login", form);
      setAuth(data.access_token, data.role, data.full_name);
      nav("/");
    } catch {
      setError("用户名或密码错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", background: "radial-gradient(circle at 30% 20%, #0b2a3a, #03101a)" }}>
      <Card style={{ width: 380 }}>
        <Title level={3} style={{ textAlign: "center", marginBottom: 4 }}>
          ⚡ 机组能效优化
        </Title>
        <Paragraph type="secondary" style={{ textAlign: "center" }}>
          燃煤机组能效与智能燃烧优化系统
        </Paragraph>
        {error && <Alert type="error" message={error} style={{ marginBottom: 12 }} />}
        <Form layout="vertical" onFinish={onFinish} initialValues={{ username: "energyeng", password: "demo123" }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input size="large" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            登录
          </Button>
        </Form>
        <Text type="secondary" style={{ display: "block", marginTop: 12, fontSize: 12 }}>
          演示账号：admin / operator / energyeng / manager / viewer，密码均为 demo123
        </Text>
      </Card>
    </div>
  );
}
