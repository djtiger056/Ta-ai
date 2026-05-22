import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Button, Space, Divider } from 'antd'
import {
  MessageOutlined,
  SettingOutlined,
  UserOutlined,
  RobotOutlined,
  SoundOutlined,
  PictureOutlined,
  VideoCameraOutlined,
  DatabaseOutlined,
  EyeOutlined,
  BellOutlined,
  HighlightOutlined,
  SmileOutlined,
  ClockCircleOutlined,
  ScheduleOutlined,
  ToolOutlined,
  LogoutOutlined,
  CrownOutlined,
  GlobalOutlined,
  DashboardOutlined,
  RocketOutlined,
  BookOutlined,
} from '@ant-design/icons'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'
import UserSettingsPage from './pages/UserSettingsPage'
import PersonalityPage from './pages/PersonalityPage'
import TTSConfigPage from './pages/TTSConfigPage.tsx'
import ImageGenPage from './pages/ImageGenPage'
import VideoGenPage from './pages/VideoGenPage'
import MemoryPage from './pages/MemoryPage'
import VisionPage from './pages/VisionPage'
import { useNavigate, useLocation } from 'react-router-dom'
import PromptEnhancerPage from './pages/PromptEnhancerPage'
import DailySchedulePage from './pages/DailySchedulePage'
import EmotePage from './pages/EmotePage'
import ReminderPage from './pages/ReminderPage'
import CerebellumPage from './pages/CerebellumPage'
import AgentDelegatePage from './pages/AgentDelegatePage'
import AdminUsersPage from './pages/AdminUsersPage'
import LoginPage from './pages/LoginPage'
import AdminGlobalConfigPage from './pages/AdminGlobalConfigPage'
import RoleplayModePage from './pages/RoleplayModePage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'

const { Header, Sider, Content } = Layout

// 主应用布局组件
const MainLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAdmin, logout } = useAuth()

  // 普通用户菜单项
  const userMenuItems = [
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: '聊天测试',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '我的设置',
    },
    {
      key: '/personality',
      icon: <UserOutlined />,
      label: '人格设定',
    },
    {
      key: '/roleplay-mode',
      icon: <BookOutlined />,
      label: '情景模式',
    },
    {
      key: '/tts',
      icon: <SoundOutlined />,
      label: 'TTS配置',
    },
    {
      key: '/image-gen',
      icon: <PictureOutlined />,
      label: '图像生成',
    },
    {
      key: '/video-gen',
      icon: <VideoCameraOutlined />,
      label: '视频生成',
    },
    {
      key: '/prompt-enhancer',
      icon: <HighlightOutlined />,
      label: '提示词增强',
    },
    {
      key: '/emotes',
      icon: <SmileOutlined />,
      label: '表情包管理',
    },
    {
      key: '/daily-schedule',
      icon: <ScheduleOutlined />,
      label: '作息生成',
    },
    {
      key: '/memory',
      icon: <DatabaseOutlined />,
      label: '记忆管理',
    },
    {
      key: '/vision',
      icon: <EyeOutlined />,
      label: '视觉识别',
    },
    {
      key: '/reminder',
      icon: <ClockCircleOutlined />,
      label: '待办事项',
    },
    {
      key: '/cerebellum',
      icon: <DashboardOutlined />,
      label: '情绪系统',
    },
    {
      key: '/agent-delegate',
      icon: <RocketOutlined />,
      label: 'Agent委派',
    },
  ]

  // 管理员专属菜单项
  const adminMenuItems = [
    {
      key: 'admin-divider',
      type: 'divider' as const,
    },
    {
      key: 'admin-group',
      type: 'group' as const,
      label: '管理员功能',
      children: [
        {
          key: '/admin/global-config',
          icon: <GlobalOutlined />,
          label: '全局配置',
        },
        {
          key: '/admin/users',
          icon: <ToolOutlined />,
          label: '用户管理',
        },
      ],
    },
  ]

  // 根据用户角色组合菜单
  const menuItems = isAdmin ? [...userMenuItems, ...adminMenuItems] : userMenuItems

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key !== 'admin-divider' && key !== 'admin-group') {
      navigate(key)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // 用户下拉菜单
  const userDropdownItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: `${user?.nickname || user?.username}`,
      disabled: true,
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={200}>
        <div className="logo">
          <RobotOutlined /> LFBot
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout>
        <Header style={{ 
          background: '#fff', 
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '18px',
          fontWeight: 'bold',
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
        }}>
          <span>LFBot 管理界面</span>
          <Space>
            {isAdmin && (
              <span style={{ 
                fontSize: '12px', 
                color: '#faad14',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}>
                <CrownOutlined /> 管理员
              </span>
            )}
            <Dropdown menu={{ items: userDropdownItems }} placement="bottomRight">
              <Button type="text" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Avatar 
                  size="small" 
                  icon={<UserOutlined />}
                  src={user?.avatar}
                />
                <span>{user?.nickname || user?.username}</span>
              </Button>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: '24px 16px 0', overflow: 'auto' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/settings" element={<UserSettingsPage />} />
            <Route path="/personality" element={<PersonalityPage />} />
            <Route path="/roleplay-mode" element={<RoleplayModePage />} />
            <Route path="/tts" element={<TTSConfigPage />} />
            <Route path="/image-gen" element={<ImageGenPage />} />
            <Route path="/video-gen" element={<VideoGenPage />} />
            <Route path="/prompt-enhancer" element={<PromptEnhancerPage />} />
            <Route path="/emotes" element={<EmotePage />} />
            <Route path="/daily-schedule" element={<DailySchedulePage />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/vision" element={<VisionPage />} />
            <Route path="/reminder" element={<ReminderPage />} />
            <Route path="/cerebellum" element={<CerebellumPage />} />
            <Route path="/agent-delegate" element={<AgentDelegatePage />} />
            {/* 管理员路由 */}
            <Route path="/admin/global-config" element={
              <ProtectedRoute requireAdmin>
                <AdminGlobalConfigPage />
              </ProtectedRoute>
            } />
            <Route path="/admin/users" element={
              <ProtectedRoute requireAdmin>
                <AdminUsersPage />
              </ProtectedRoute>
            } />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

// 应用根组件
const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={
        <ProtectedRoute>
          <MainLayout />
        </ProtectedRoute>
      } />
    </Routes>
  )
}

const AppWrapper: React.FC = () => (
  <Router>
    <AuthProvider>
      <App />
    </AuthProvider>
  </Router>
)

export default AppWrapper
