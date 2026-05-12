import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

/**
 * 路由守卫组件
 * - 未登录用户重定向到登录页
 * - requireAdmin=true 时，非管理员用户重定向到首页
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, requireAdmin = false }) => {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();
  const location = useLocation();

  // 加载中显示 loading
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
      }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  // 未登录，重定向到登录页
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 需要管理员权限但用户不是管理员
  if (requireAdmin && !isAdmin) {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
