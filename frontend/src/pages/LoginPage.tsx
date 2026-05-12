import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Tabs, Typography, Space, Divider } from 'antd';
import { UserOutlined, LockOutlined, SmileOutlined, QqOutlined, CrownOutlined, RobotOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text, Paragraph } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('login');
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register } = useAuth();

  // 获取登录前的页面路径
  const from = (location.state as any)?.from?.pathname || '/chat';

  const handleLogin = async (values: any) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success('登录成功！');
      navigate(from, { replace: true });
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdminLogin = async (values: any) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      // 检查是否为管理员
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        if (user.is_admin !== 1) {
          message.warning('该账号不是管理员，已以普通用户身份登录');
        } else {
          message.success('管理员登录成功！');
        }
      }
      navigate(from, { replace: true });
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: any) => {
    setLoading(true);
    try {
      await register({
        username: values.username,
        password: values.password,
        nickname: values.nickname,
        qq_user_id: values.qq_user_id,
      });
      message.success('注册成功！请登录');
      setActiveTab('login');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* 背景装饰 */}
      <div style={{
        position: 'absolute',
        top: '-50%',
        left: '-50%',
        width: '200%',
        height: '200%',
        background: 'radial-gradient(circle at 30% 50%, rgba(100, 130, 255, 0.08) 0%, transparent 50%), radial-gradient(circle at 70% 80%, rgba(180, 100, 255, 0.06) 0%, transparent 40%)',
        animation: 'float 20s ease-in-out infinite',
      }} />

      <Card
        style={{
          width: 440,
          borderRadius: '16px',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3), 0 0 40px rgba(100, 130, 255, 0.1)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(20px)',
        }}
        bodyStyle={{ padding: '32px 32px 24px' }}
      >
        {/* Logo 区域 */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '12px',
            boxShadow: '0 8px 24px rgba(102, 126, 234, 0.4)',
          }}>
            <RobotOutlined style={{ fontSize: '32px', color: '#fff' }} />
          </div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#1a1a2e' }}>
            LFBot
          </Title>
          <Text type="secondary" style={{ fontSize: '13px' }}>
            AI 聊天机器人管理系统
          </Text>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          centered
          size="small"
          items={[
            {
              key: 'login',
              label: '用户登录',
              children: (
                <Form
                  name="login"
                  onFinish={handleLogin}
                  autoComplete="off"
                  size="large"
                  style={{ marginTop: '8px' }}
                >
                  <Form.Item
                    name="username"
                    rules={[{ required: true, message: '请输入用户名' }]}
                  >
                    <Input
                      prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="用户名"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="password"
                    rules={[{ required: true, message: '请输入密码' }]}
                  >
                    <Input.Password
                      prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="密码"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item style={{ marginBottom: '12px' }}>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={loading}
                      block
                      style={{
                        borderRadius: '8px',
                        height: '44px',
                        fontSize: '15px',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
                      }}
                    >
                      登录
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: '注册账号',
              children: (
                <Form
                  name="register"
                  onFinish={handleRegister}
                  autoComplete="off"
                  size="large"
                  style={{ marginTop: '8px' }}
                >
                  <Form.Item
                    name="username"
                    rules={[
                      { required: true, message: '请输入用户名' },
                      { min: 3, message: '用户名至少3个字符' },
                      { max: 50, message: '用户名最多50个字符' },
                      { pattern: /^[a-zA-Z0-9_\u4e00-\u9fa5]+$/, message: '用户名只能包含字母、数字、下划线和中文' }
                    ]}
                  >
                    <Input
                      prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="用户名"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="password"
                    rules={[
                      { required: true, message: '请输入密码' },
                      { min: 6, message: '密码至少6个字符' }
                    ]}
                  >
                    <Input.Password
                      prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="密码"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="confirmPassword"
                    dependencies={['password']}
                    rules={[
                      { required: true, message: '请确认密码' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('password') === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error('两次输入的密码不一致'));
                        },
                      }),
                    ]}
                  >
                    <Input.Password
                      prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="确认密码"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item name="nickname">
                    <Input
                      prefix={<SmileOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="昵称（可选）"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="qq_user_id"
                    rules={[
                      { pattern: /^\d*$/, message: 'QQ号只能是数字' }
                    ]}
                  >
                    <Input
                      prefix={<QqOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="QQ号（可选，用于QQ聊天绑定）"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item style={{ marginBottom: '12px' }}>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={loading}
                      block
                      style={{
                        borderRadius: '8px',
                        height: '44px',
                        fontSize: '15px',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
                      }}
                    >
                      注册
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'admin',
              label: (
                <span>
                  <CrownOutlined style={{ marginRight: 4 }} />
                  管理员
                </span>
              ),
              children: (
                <Form
                  name="admin_login"
                  onFinish={handleAdminLogin}
                  autoComplete="off"
                  size="large"
                  style={{ marginTop: '8px' }}
                >
                  <div style={{
                    background: 'linear-gradient(135deg, #fff7e6 0%, #fff1f0 100%)',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    marginBottom: '16px',
                    border: '1px solid #ffd591',
                  }}>
                    <Text style={{ fontSize: '12px', color: '#ad6800' }}>
                      <CrownOutlined style={{ marginRight: 4 }} />
                      管理员可以配置全局默认设置，管理所有用户。首次使用请先注册账号，然后在数据库中将 is_admin 设为 1。
                    </Text>
                  </div>

                  <Form.Item
                    name="username"
                    rules={[{ required: true, message: '请输入管理员用户名' }]}
                  >
                    <Input
                      prefix={<CrownOutlined style={{ color: '#faad14' }} />}
                      placeholder="管理员用户名"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="password"
                    rules={[{ required: true, message: '请输入密码' }]}
                  >
                    <Input.Password
                      prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="密码"
                      style={{ borderRadius: '8px' }}
                    />
                  </Form.Item>

                  <Form.Item style={{ marginBottom: '12px' }}>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={loading}
                      block
                      style={{
                        borderRadius: '8px',
                        height: '44px',
                        fontSize: '15px',
                        background: 'linear-gradient(135deg, #fa8c16 0%, #fa541c 100%)',
                        border: 'none',
                        boxShadow: '0 4px 12px rgba(250, 140, 22, 0.4)',
                      }}
                    >
                      <CrownOutlined /> 管理员登录
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />

        {/* 底部信息 */}
        <div style={{ textAlign: 'center', marginTop: '8px' }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            登录后可配置专属的 AI 机器人设置
          </Text>
        </div>
      </Card>

      {/* CSS 动画 */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-20px) rotate(1deg); }
        }
      `}</style>
    </div>
  );
};

export default LoginPage;
