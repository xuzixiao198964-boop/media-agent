import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, Alert, Space, Checkbox } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { login } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;

interface LoginFormData {
  username: string;
  password: string;
  remember: boolean;
}

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setToken = useAuthStore((state) => state.setToken);
  const setRememberMe = useAuthStore((state) => state.setRememberMe);

  const onFinish = async (values: LoginFormData) => {
    setLoading(true);
    setError(null);

    try {
      // 调用登录API
      const response = await login({
        username: values.username,
        password: values.password,
      });

      if (response.access_token) {
        // 保存令牌
        setToken(
          response.access_token,
          response.refresh_token
        );

        // 保存记住我设置
        setRememberMe(values.remember);

        // 跳转到首页
        navigate('/dashboard');
      } else {
        setError('登录失败');
      }
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail;
      
      if (errorDetail === '用户名或密码错误') {
        setError('用户名或密码错误');
      } else if (errorDetail?.includes('锁定')) {
        setError('账户已被锁定，请稍后再试');
      } else if (errorDetail?.includes('限制')) {
        setError('登录失败次数过多，请稍后再试');
      } else {
        setError(errorDetail || '登录失败，请稍后重试');
      }
    } finally {
      setLoading(false);
    }
  };

  const validateUsername = (_: any, value: string) => {
    if (!value) {
      return Promise.reject('请输入用户名');
    }
    
    // 用户名规则：3-64字符，只允许字母、数字、下划线
    const usernameRegex = /^[a-zA-Z0-9_]{3,64}$/;
    if (!usernameRegex.test(value)) {
      return Promise.reject('用户名格式不正确');
    }
    
    return Promise.resolve();
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      backgroundColor: '#f0f2f5',
      padding: '20px'
    }}>
      <Card style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={2}>登录账号</Title>
          <Text type="secondary">欢迎回到 Media Agent</Text>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            style={{ marginBottom: 24 }}
            closable
            onClose={() => setError(null)}
          />
        )}

        <Form
          form={form}
          name="login"
          initialValues={{ remember: true }}
          onFinish={onFinish}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { validator: validateUsername }
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="请输入用户名"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' }
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </Form.Item>

          <Form.Item>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox>记住我</Checkbox>
              </Form.Item>
              
              <Link to="/forgot-password">
                <Button type="link" style={{ padding: 0 }}>
                  忘记密码？
                </Button>
              </Link>
            </div>
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
            >
              登录
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center' }}>
            <Space>
              <Text>还没有账号？</Text>
              <Link to="/register">
                <Button type="link" style={{ padding: 0 }}>
                  立即注册
                </Button>
              </Link>
            </Space>
          </div>
        </Form>

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            安全提示：请勿在公共设备上勾选"记住我"，定期修改密码以确保账户安全。
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default LoginPage;