import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// 用户信息类型
export interface User {
  id: number;
  username: string;
  nickname: string | null;
  qq_user_id: string | null;
  avatar: string | null;
  is_active: number;
  is_admin: number;
  created_at: string;
}

// 认证上下文类型
interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

interface RegisterData {
  username: string;
  password: string;
  nickname?: string;
  qq_user_id?: string;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// 配置 axios 拦截器
const setupAxiosInterceptors = (token: string | null, logout: () => void) => {
  // 请求拦截器：添加 token
  axios.interceptors.request.use(
    (config) => {
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // 响应拦截器：处理 401 错误
  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        // Token 过期或无效，自动登出
        logout();
      }
      return Promise.reject(error);
    }
  );
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  }, []);

  // 初始化时从 localStorage 恢复状态
  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    
    if (storedToken && storedUser) {
      try {
        const parsedUser = JSON.parse(storedUser);
        setToken(storedToken);
        setUser(parsedUser);
        
        // 设置 axios 默认 header
        axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
      } catch (e) {
        // 解析失败，清除存储
        logout();
      }
    }
    
    setIsLoading(false);
  }, [logout]);

  // 设置 axios 拦截器
  useEffect(() => {
    setupAxiosInterceptors(token, logout);
  }, [token, logout]);

  const login = async (username: string, password: string) => {
    const response = await axios.post('/api/auth/login', { username, password });
    const { access_token, user: userData } = response.data;
    
    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));
    
    setToken(access_token);
    setUser(userData);
    
    // 设置 axios 默认 header
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
  };

  const register = async (data: RegisterData) => {
    await axios.post('/api/auth/register', data);
  };

  const refreshUser = async () => {
    if (!token) return;
    
    try {
      const response = await axios.get('/api/auth/me');
      const userData = response.data;
      localStorage.setItem('user', JSON.stringify(userData));
      setUser(userData);
    } catch (error) {
      // 刷新失败，可能 token 已过期
      logout();
    }
  };

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    isAdmin: user?.is_admin === 1,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
