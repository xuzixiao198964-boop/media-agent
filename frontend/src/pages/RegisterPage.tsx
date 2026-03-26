import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, Alert, Space } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { register } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;

interface RegisterFormData {
  username: string;
  password: string;
  confirmPassword: string;
}

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setToken = useAuthStore((state) => state.setToken);

  const onFinish = async (values: RegisterFormData) => {
    setLoading(true);
    setError(null);

    try {
      // 调用注册API
      const response = await register({
        username: values.username,
        password: values.password,
      });

      if (response.success) {
        // 保存令牌
        setToken(
          response.data.access_token,
          response.data.refresh_token
        );

        // 跳转到首页
        navigate('/dashboard');
      } else {
        setError(response.message || '注册失败');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '注册失败，请稍后重试');
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
      return Promise.reject('用户名必须是3-64个字符，只能包含字母、数字和下划线');
    }
    
    return Promise.resolve();
  };

  const validatePassword = (_: any, value: string) => {
    if (!value) {
      return Promise.reject('请输入密码');
    }
    
    // 密码规则：12-128字符，必须包含4种字符类型
    if (value.length < 12 || value.length > 128) {
      return Promise.reject('密码长度必须在12-128个字符之间');
    }
    
    // 检查字符类型
    const hasUpperCase = /[A-Z]/.test(value);
    const hasLowerCase = /[a-z]/.test(value);
    const hasNumbers = /\d/.test(value);
    const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(value);
    
    const typeCount = [hasUpperCase, hasLowerCase, hasNumbers, hasSpecialChar].filter(Boolean).length;
    
    if (typeCount < 4) {
      return Promise.reject('密码必须包含大写字母、小写字母、数字和特殊字符');
    }
    
    return Promise.resolve();
  };

  const validateConfirmPassword = ({ getFieldValue }: any, value: string) => {
    if (!value || getFieldValue('password') === value) {
      return Promise.resolve();
    }
    return Promise.reject('两次输入的密码不一致');
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
          <Title level={2}>注册账号</Title>
          <Text type="secondary">创建您的 Media Agent 账号</Text>
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
          name="register"
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
              { required: true, message: '请输入密码' },
              { validator: validatePassword }
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请输入密码"
              autoComplete="new-password"
            />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            label="确认密码"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              { validator: validateConfirmPassword }
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请再次输入密码"
              autoComplete="new-password"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
            >
              注册
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center' }}>
            <Space>
              <Text>已有账号？</Text>
              <Link to="/login">
                <Button type="link" style={{ padding: 0 }}>
                  立即登录
                </Button>
              </Link>
            </Space>
          </div>
        </Form>

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            注册即表示您同意我们的服务条款和隐私政策。您的密码会使用bcrypt算法加密存储。
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default RegisterPage;