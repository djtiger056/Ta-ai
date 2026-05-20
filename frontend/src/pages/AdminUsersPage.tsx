import React, { useEffect, useMemo, useState } from 'react'
import { 
  Card, Input, Button, Table, Space, message, Typography, Modal, 
  Form, Tabs, Row, Col, Select, Switch, Divider, Alert, Tag, 
  Tooltip, Popconfirm, Descriptions, Badge, Transfer, Empty
} from 'antd'
import { 
  SaveOutlined, ReloadOutlined, EyeOutlined, PlusOutlined, 
  DeleteOutlined, CopyOutlined, CheckCircleOutlined, CloseCircleOutlined,
  SafetyOutlined, UserDeleteOutlined
} from '@ant-design/icons'
import api from '@/services/api'

const { Title, Text } = Typography
const { TextArea } = Input
const { Option } = Select

type AdminUserSummary = {
  id: number
  username: string
  nickname?: string
  qq_user_id?: string
  is_active: number
  is_admin: number
  created_at: string
}

type AccessControlConfig = {
  enabled: boolean
  mode: string
  whitelist: string[]
  blacklist: string[]
  deny_message: string
}

const AdminUsersPage: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [users, setUsers] = useState<AdminUserSummary[]>([])
  const [selectedUser, setSelectedUser] = useState<AdminUserSummary | null>(null)
  const [configModalOpen, setConfigModalOpen] = useState(false)
  const [configLoading, setConfigLoading] = useState(false)
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [previewData, setPreviewData] = useState<any>(null)
  const [activeTab, setActiveTab] = useState('users')
  const [addUserModalOpen, setAddUserModalOpen] = useState(false)
  const [addUserForm] = Form.useForm()
  const [configForm] = Form.useForm()
  
  // 白黑名单相关状态
  const [accessControl, setAccessControl] = useState<AccessControlConfig>({
    enabled: false,
    mode: 'disabled',
    whitelist: [],
    blacklist: [],
    deny_message: '抱歉，你没有权限使用此机器人。'
  })
  const [accessControlLoading, setAccessControlLoading] = useState(false)
  const [linyuSessions, setLinyuSessions] = useState<Record<string, any>>({})

  const loadUsers = async () => {
    setLoading(true)
    try {
      const resp = await api.get('/admin/users', { params: { limit: 200, skip: 0 } })
      setUsers(resp.data.users || [])
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  const loadAccessControl = async () => {
    setAccessControlLoading(true)
    try {
      const resp = await api.get('/access-control')
      setAccessControl(resp.data)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载访问控制配置失败')
    } finally {
      setAccessControlLoading(false)
    }
  }

  const loadLinyuSessions = async () => {
    try {
      const resp = await api.get('/admin/linyu-sessions')
      setLinyuSessions(resp.data.sessions || {})
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载 Linyu 会话状态失败')
    }
  }

  const refreshLinyuSession = async (userId?: number) => {
    try {
      if (userId) {
        await api.post(`/admin/linyu-sessions/${userId}/refresh`)
      } else {
        await api.post('/admin/linyu-sessions/refresh')
      }
      message.success(userId ? `已提交用户 ${userId} 的 Linyu 会话热重载` : '已提交全部 Linyu 会话热重载')
      window.setTimeout(() => {
        loadLinyuSessions()
      }, 1200)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提交 Linyu 热重载失败')
    }
  }

  const updateAccessControl = async (values: Partial<AccessControlConfig>) => {
    setAccessControlLoading(true)
    try {
      await api.put('/access-control', { ...accessControl, ...values })
      message.success('访问控制配置已更新')
      loadAccessControl()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    } finally {
      setAccessControlLoading(false)
    }
  }

  const openConfigEditor = async (user: AdminUserSummary) => {
    setSelectedUser(user)
    setConfigModalOpen(true)
    setConfigLoading(true)
    setActiveTab('users')
    try {
      const key = user.qq_user_id || String(user.id)
      const resp = await api.get(`/admin/users/${encodeURIComponent(key)}/config`, {
        params: { merged: false },
      })
      const overrides = resp.data.overrides || {}
      configForm.setFieldsValue(overrides)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载用户配置失败')
      configForm.setFieldsValue({})
    } finally {
      setConfigLoading(false)
    }
  }

  const previewMergedConfig = async (user: AdminUserSummary) => {
    setSelectedUser(user)
    setPreviewModalOpen(true)
    setConfigLoading(true)
    try {
      const key = user.qq_user_id || String(user.id)
      const resp = await api.get(`/admin/users/${encodeURIComponent(key)}/config`, {
        params: { merged: true },
      })
      setPreviewData(resp.data.merged || {})
    } catch (e: any) {
      message.error(e.response?.data?.detail || '加载配置失败')
      setPreviewData({})
    } finally {
      setConfigLoading(false)
    }
  }

  const saveUserConfig = async () => {
    if (!selectedUser) return

    try {
      const values = await configForm.validateFields()
      setConfigLoading(true)
      const key = selectedUser.qq_user_id || String(selectedUser.id)
      await api.put(`/admin/users/${encodeURIComponent(key)}/config`, values)
      message.success('配置已保存')
      setConfigModalOpen(false)
    } catch (e: any) {
      if (e.errorFields) {
        message.error('表单验证失败，请检查输入')
      } else {
        message.error(e.response?.data?.detail || '保存失败')
      }
    } finally {
      setConfigLoading(false)
    }
  }

  const handleAddUser = async () => {
    try {
      const values = await addUserForm.validateFields()
      setConfigLoading(true)
      await api.post('/admin/users/qq/upsert', values)
      message.success('用户添加成功')
      setAddUserModalOpen(false)
      addUserForm.resetFields()
      loadUsers()
    } catch (e: any) {
      if (e.errorFields) {
        message.error('表单验证失败')
      } else {
        message.error(e.response?.data?.detail || '添加失败')
      }
    } finally {
      setConfigLoading(false)
    }
  }

  const handleDeleteUser = async (user: AdminUserSummary) => {
    try {
      const key = user.qq_user_id || String(user.id)
      await api.delete(`/admin/users/${encodeURIComponent(key)}`)
      message.success(`用户 ${user.nickname || user.username} 已删除`)
      loadUsers()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const resetConfigSection = (section: string) => {
    Modal.confirm({
      title: '确认重置',
      content: `确定要重置该用户的【${section}】配置吗？重置后将使用全局默认配置。`,
      okText: '确认',
      cancelText: '取消',
      onOk: () => {
        const currentValue = configForm.getFieldsValue()
        const newValue = { ...currentValue }
        newValue[section] = undefined
        configForm.setFieldsValue(newValue)
        message.success(`${section} 配置已重置`)
      },
    })
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  }

  // 获取所有用户的QQ号列表用于Transfer组件
  const allUserQQIds = useMemo(() => {
    return users
      .filter(u => u.qq_user_id)
      .map(u => ({
        key: u.qq_user_id!,
        title: `${u.qq_user_id} (${u.nickname || u.username})`
      }))
  }, [users])

  useEffect(() => {
    loadUsers()
    loadLinyuSessions()
  }, [])

  const handleTabChange = (key: string) => {
    setActiveTab(key)
    if (key === 'access_control' && !accessControlLoading) {
      loadAccessControl()
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>多用户配置管理（管理员）</Title>
      
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert
            message="配置说明"
            description={
              <div>
                <p>1. 每个QQ用户可以有独立的配置覆盖，未设置的配置项将自动继承全局 config.yaml 中的值。</p>
                <p>2. 点击"编辑配置"为用户设置个性化配置，点击"预览配置"查看合并后的完整配置。</p>
                <p>3. 配置留空表示使用全局默认值。</p>
                <p>4. 白黑名单功能用于控制哪些QQ用户可以使用机器人。</p>
              </div>
            }
            type="info"
            showIcon
          />
          <Space wrap>
            <Button type="primary" loading={loading} onClick={loadUsers}>
              刷新用户列表
            </Button>
            <Button onClick={loadLinyuSessions}>
              刷新 Linyu 状态
            </Button>
            <Button onClick={() => refreshLinyuSession()}>
              热重载全部 Linyu 会话
            </Button>
            <Button icon={<PlusOutlined />} onClick={() => setAddUserModalOpen(true)}>
              添加QQ用户
            </Button>
          </Space>
        </Space>
      </Card>

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          items={[
            {
              key: 'users',
              label: '用户列表',
              children: (
                <Table
                  rowKey="id"
                  loading={loading}
                  dataSource={users}
                  columns={[
                    { 
                      title: 'ID', 
                      dataIndex: 'id', 
                      width: 80,
                      render: (id) => <Text code>{id}</Text>
                    },
                    { 
                      title: 'QQ号', 
                      dataIndex: 'qq_user_id', 
                      width: 140,
                      render: (qq) => qq ? <Tag color="blue">{qq}</Tag> : <Text type="secondary">未绑定</Text>
                    },
                    {
                      title: 'Linyu 会话',
                      dataIndex: 'id',
                      width: 240,
                      render: (id: number) => {
                        const session = linyuSessions[String(id)]
                        if (!session) {
                          return <Text type="secondary">未启用</Text>
                        }
                        return (
                          <Space direction="vertical" size={2}>
                            <Space size={6}>
                              <Badge status={session.connected ? 'success' : (session.running ? 'processing' : 'default')} />
                              <Text>{session.connected ? '已连接' : (session.running ? '启动中' : '未连接')}</Text>
                            </Space>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              AI: {session.login_account || '未配置'}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              对象: {session.target_user_account || session.target_user_id || '未配置'}
                            </Text>
                            {session.last_error ? (
                              <Tooltip title={session.last_error}>
                                <Text type="danger" style={{ fontSize: 12 }}>最近错误</Text>
                              </Tooltip>
                            ) : null}
                          </Space>
                        )
                      }
                    },
                    { 
                      title: '昵称', 
                      dataIndex: 'nickname', 
                      width: 160,
                      render: (nick, record) => nick || record.username
                    },
                    { 
                      title: '状态', 
                      dataIndex: 'is_active', 
                      width: 80,
                      render: (active) => active ? (
                        <Badge status="success" text="启用" />
                      ) : (
                        <Badge status="error" text="禁用" />
                      )
                    },
                    { 
                      title: '管理员', 
                      dataIndex: 'is_admin', 
                      width: 80,
                      render: (isAdmin) => isAdmin ? (
                        <Tag color="red">管理员</Tag>
                      ) : null
                    },
                    { 
                      title: '创建时间', 
                      dataIndex: 'created_at', 
                      width: 180,
                      render: (time) => new Date(time).toLocaleString('zh-CN')
                    },
                    {
                      title: '操作',
                      key: 'action',
                      width: 280,
                      fixed: 'right' as const,
                      render: (_: any, record: AdminUserSummary) => (
                        <Space size="small">
                          <Button 
                            size="small" 
                            icon={<EyeOutlined />} 
                            onClick={() => previewMergedConfig(record)}
                          >
                            预览
                          </Button>
                          <Button 
                            type="primary" 
                            size="small" 
                            onClick={() => openConfigEditor(record)}
                          >
                            编辑配置
                          </Button>
                          <Button
                            size="small"
                            onClick={() => refreshLinyuSession(record.id)}
                          >
                            重载 Linyu
                          </Button>
                          <Popconfirm
                            title="确认删除"
                            description={`确定要删除用户 ${record.nickname || record.username} 吗？此操作不可恢复！`}
                            onConfirm={() => handleDeleteUser(record)}
                            okText="确认"
                            cancelText="取消"
                          >
                            <Button 
                              size="small" 
                              danger 
                              icon={<UserDeleteOutlined />}
                            >
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                  pagination={{ pageSize: 20 }}
                  scroll={{ x: 1100 }}
                />
              ),
            },
            {
              key: 'access_control',
              label: '白黑名单',
              icon: <SafetyOutlined />,
              children: (
                <div>
                  <Alert
                    message="访问控制说明"
                    description={
                      <div>
                        <p>• <strong>白名单模式</strong>：只有白名单中的用户可以使用机器人</p>
                        <p>• <strong>黑名单模式</strong>：黑名单中的用户将被拒绝访问</p>
                        <p>• <strong>关闭模式</strong>：所有用户都可以使用机器人</p>
                      </div>
                    }
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  
                  <Form layout="vertical" initialValues={accessControl}>
                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item label="启用访问控制">
                          <Switch 
                            checked={accessControl.enabled}
                            onChange={(checked) => updateAccessControl({ enabled: checked })}
                          />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item label="控制模式">
                          <Select
                            value={accessControl.mode}
                            onChange={(value) => updateAccessControl({ mode: value })}
                            disabled={!accessControl.enabled}
                            style={{ width: '100%' }}
                          >
                            <Option value="disabled">关闭（所有人可用）</Option>
                            <Option value="whitelist">白名单（仅白名单用户可用）</Option>
                            <Option value="blacklist">黑名单（黑名单用户不可用）</Option>
                          </Select>
                        </Form.Item>
                      </Col>
                    </Row>

                    <Divider titlePlacement="left">白名单管理</Divider>
                    <Form.Item label="白名单用户">
                      <Transfer
                        dataSource={allUserQQIds}
                        titles={['所有用户', '白名单']}
                        targetKeys={accessControl.whitelist}
                        onChange={(targetKeys) => updateAccessControl({ whitelist: targetKeys as string[] })}
                        render={(item) => item.title}
                        oneWay={false}
                        style={{ marginBottom: 16 }}
                        disabled={!accessControl.enabled || accessControl.mode !== 'whitelist'}
                      />
                      <div style={{ marginTop: 8 }}>
                        <Input.Search
                          placeholder="直接输入QQ号添加到白名单"
                          enterButton="添加"
                          size="small"
                          style={{ width: 280 }}
                          onSearch={(qq) => {
                            if (qq && !accessControl.whitelist.includes(qq)) {
                              updateAccessControl({ whitelist: [...accessControl.whitelist, qq] })
                            }
                          }}
                          disabled={!accessControl.enabled || accessControl.mode !== 'whitelist'}
                        />
                      </div>
                    </Form.Item>

                    <Divider titlePlacement="left">黑名单管理</Divider>
                    <Form.Item label="黑名单用户">
                      <Transfer
                        dataSource={allUserQQIds}
                        titles={['所有用户', '黑名单']}
                        targetKeys={accessControl.blacklist}
                        onChange={(targetKeys) => updateAccessControl({ blacklist: targetKeys as string[] })}
                        render={(item) => item.title}
                        oneWay={false}
                        disabled={!accessControl.enabled || accessControl.mode !== 'blacklist'}
                      />
                      <div style={{ marginTop: 8 }}>
                        <Input.Search
                          placeholder="直接输入QQ号添加到黑名单"
                          enterButton="添加"
                          size="small"
                          style={{ width: 280 }}
                          onSearch={(qq) => {
                            if (qq && !accessControl.blacklist.includes(qq)) {
                              updateAccessControl({ blacklist: [...accessControl.blacklist, qq] })
                            }
                          }}
                          disabled={!accessControl.enabled || accessControl.mode !== 'blacklist'}
                        />
                      </div>
                    </Form.Item>

                    <Form.Item label="拒绝消息">
                      <TextArea
                        rows={2}
                        value={accessControl.deny_message}
                        onChange={(e) => updateAccessControl({ deny_message: e.target.value })}
                        disabled={!accessControl.enabled}
                      />
                    </Form.Item>
                  </Form>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* 添加用户弹窗 */}
      <Modal
        title="添加QQ用户"
        open={addUserModalOpen}
        onOk={handleAddUser}
        onCancel={() => {
          setAddUserModalOpen(false)
          addUserForm.resetFields()
        }}
        confirmLoading={configLoading}
        okText="添加"
        cancelText="取消"
      >
        <Form form={addUserForm} layout="vertical">
          <Form.Item
            name="qq_user_id"
            label="QQ号"
            rules={[{ required: true, message: '请输入QQ号' }]}
          >
            <Input placeholder="请输入QQ号" />
          </Form.Item>
          <Form.Item name="nickname" label="昵称（可选）">
            <Input placeholder="请输入昵称" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 配置编辑弹窗 */}
      <Modal
        title={
          <Space>
            <span>编辑配置：{selectedUser?.qq_user_id || selectedUser?.username}</span>
            <Tooltip title="预览合并后的完整配置">
              <Button 
                size="small" 
                icon={<EyeOutlined />} 
                onClick={() => previewMergedConfig(selectedUser!)}
              >
                预览
              </Button>
            </Tooltip>
          </Space>
        }
        open={configModalOpen}
        onCancel={() => setConfigModalOpen(false)}
        onOk={saveUserConfig}
        confirmLoading={configLoading}
        width={900}
        okText="保存配置"
        cancelText="取消"
        destroyOnClose
      >
        <Alert
          message="配置说明"
          description="留空的字段将使用全局默认配置。点击右侧重置按钮可重置该模块配置。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        
        <Form form={configForm} layout="vertical">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'system_prompt',
                label: '系统提示词',
                children: (
                  <div>
                    <Form.Item name="system_prompt" label="自定义系统提示词">
                      <TextArea
                        rows={10}
                        placeholder="留空使用全局默认提示词..."
                      />
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('system_prompt')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'llm',
                label: 'LLM配置',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['llm', 'provider']} label="提供商">
                          <Select placeholder="选择提供商" allowClear>
                            <Option value="openai">OpenAI</Option>
                            <Option value="siliconflow">硅基流动</Option>
                            <Option value="deepseek">DeepSeek</Option>
                            <Option value="yunwu">云舞</Option>
                            <Option value="qwen">千问（DashScope）</Option>
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['llm', 'model']} label="模型">
                          <Input placeholder="例如: gpt-4" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['llm', 'temperature']} label="Temperature">
                          <Input type="number" step="0.1" min={0} max={2} placeholder="0.7" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['llm', 'max_tokens']} label="Max Tokens">
                          <Input type="number" min={1} placeholder="2000" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name={['llm', 'api_key']} label="API Key">
                      <Input.Password placeholder="留空使用全局API Key" allowClear />
                    </Form.Item>
                    <Form.Item name={['llm', 'base_url']} label="Base URL">
                      <Input placeholder="留空使用全局Base URL" allowClear />
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('llm')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'tts',
                label: 'TTS配置',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['tts', 'enabled']} label="启用TTS" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['tts', 'voice']} label="语音">
                          <Input placeholder="语音名称" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['tts', 'speed']} label="语速">
                          <Input type="number" step="0.1" min={0.5} max={2} placeholder="1.0" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['tts', 'pitch']} label="音调">
                          <Input type="number" step={1} min={-10} max={10} placeholder="0" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name={['tts', 'api_key']} label="API Key">
                      <Input.Password placeholder="留空使用全局API Key" allowClear />
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('tts')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'image_generation',
                label: '图像生成',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'enabled']} label="启用图像生成" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'provider']} label="主提供商">
                          <Select placeholder="选择提供商" allowClear>
                            <Option value="yunwu">云舞</Option>
                            <Option value="modelscope">魔搭社区</Option>
                            <Option value="kling_api">本地 kling-api</Option>
                          </Select>
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'enable_fallback']} label="启用自动降级" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item noStyle shouldUpdate>
                          {({ getFieldValue }) => (
                            <Form.Item name={['image_generation', 'fallback_provider']} label="备用提供商">
                              <Select
                                placeholder="主提供商失败时使用"
                                allowClear
                                options={[
                                  { value: 'yunwu', label: '云舞' },
                                  { value: 'modelscope', label: '魔搭社区' },
                                  { value: 'kling_api', label: '本地 kling-api' },
                                ].filter((item) => item.value !== getFieldValue(['image_generation', 'provider']))}
                              />
                            </Form.Item>
                          )}
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'modelscope', 'api_key']} label="魔搭 API Key">
                          <Input.Password placeholder="留空使用全局 API Key" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'modelscope', 'model']} label="魔搭模型">
                          <Input placeholder="Tongyi-MAI/Z-Image-Turbo" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'yunwu', 'api_key']} label="云舞 API Key">
                          <Input.Password placeholder="留空使用全局 API Key" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'yunwu', 'model']} label="云舞模型">
                          <Input placeholder="jimeng-4.5" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'yunwu', 'api_base']} label="云舞 API 地址">
                          <Input placeholder="https://yunwu.ai/v1" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'yunwu', 'timeout']} label="云舞超时（秒）">
                          <Input type="number" placeholder="120" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Divider titlePlacement="left">kling-api 配置</Divider>
                    <Alert
                      message="kling-api 说明"
                      description="这里填写 /myproject/kling-api 暴露的接口地址。若该服务开启了 SERVER_API_KEYS，这里也要填对应 x-api-key。"
                      type="info"
                      showIcon
                      style={{ marginBottom: 16 }}
                    />
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'api_base']} label="kling-api 地址">
                          <Input placeholder="http://127.0.0.1:18080" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'api_key']} label="kling-api API Key">
                          <Input.Password placeholder="未开启鉴权可留空" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'model']} label="kling-api 模型">
                          <Input placeholder="kling-v2-1" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'size']} label="图片尺寸">
                          <Input placeholder="1024x1024" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'timeout']} label="kling-api 超时（秒）">
                          <Input type="number" placeholder="180" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'poll_interval']} label="轮询间隔（秒）">
                          <Input type="number" step="0.5" placeholder="3" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'transport']} label="传输模式">
                          <Input placeholder="web" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['image_generation', 'kling_api', 'response_format']} label="响应格式">
                          <Input placeholder="url / b64_json" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name={['image_generation', 'kling_api', 'target_url']} label="目标页面地址">
                      <Input placeholder="https://klingai.com/app/image/new" allowClear />
                    </Form.Item>
                    <Divider titlePlacement="left">触发与提示文案</Divider>
                    <Form.Item name={['image_generation', 'trigger_keywords']} label="触发关键词">
                      <Select mode="tags" placeholder="输入关键词后回车" allowClear />
                    </Form.Item>
                    <Form.Item name={['image_generation', 'generating_message']} label="生成中提示">
                      <Input placeholder="🎨 正在为你生成图片，请稍候..." allowClear />
                    </Form.Item>
                    <Form.Item name={['image_generation', 'error_message']} label="失败提示">
                      <Input placeholder="😢 图片生成失败：{error}" allowClear />
                    </Form.Item>
                    <Form.Item name={['image_generation', 'success_message']} label="成功提示">
                      <Input placeholder="✨ 图片已生成完成！" allowClear />
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('image_generation')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'vision',
                label: '视觉识别',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['vision', 'enabled']} label="启用视觉识别" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['vision', 'model']} label="模型">
                          <Input placeholder="模型名称" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name={['vision', 'api_key']} label="API Key">
                      <Input.Password placeholder="留空使用全局API Key" allowClear />
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('vision')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'prompt_enhancer',
                label: '提示词增强',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['prompt_enhancer', 'enabled']} label="启用增强" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['prompt_enhancer', 'style']} label="风格">
                          <Select placeholder="选择风格" allowClear>
                            <Option value="detailed">详细</Option>
                            <Option value="concise">简洁</Option>
                            <Option value="creative">创意</Option>
                          </Select>
                        </Form.Item>
                      </Col>
                    </Row>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('prompt_enhancer')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'emotes',
                label: '表情包',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['emotes', 'enabled']} label="启用表情包" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['emotes', 'probability']} label="发送概率">
                          <Input type="number" step={0.1} min={0} max={1} placeholder="0.3" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('emotes')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'proactive_chat',
                label: '主动聊天',
                children: (
                  <div>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['proactive_chat', 'enabled']} label="启用主动聊天" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['proactive_chat', 'check_interval_seconds']} label="检查间隔(秒)">
                          <Input type="number" min={10} placeholder="60" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Divider titlePlacement="left">每日窗口</Divider>
                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item name={['proactive_chat', 'daily_window', 'enabled']} label="启用" valuePropName="checked">
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name={['proactive_chat', 'daily_window', 'start']} label="开始时间">
                          <Input placeholder="08:00" allowClear />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name={['proactive_chat', 'daily_window', 'end']} label="结束时间">
                          <Input placeholder="10:00" allowClear />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item name={['proactive_chat', 'daily_window', 'max_messages_per_window']} label="最大消息数">
                      <Input type="number" min={1} placeholder="2" allowClear />
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('proactive_chat')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'preferences',
                label: '其他偏好',
                children: (
                  <div>
                    <Form.Item name={['preferences', 'theme']} label="主题">
                      <Input placeholder="主题设置" allowClear />
                    </Form.Item>
                    <Form.Item name={['preferences', 'language']} label="语言">
                      <Select placeholder="选择语言" allowClear>
                        <Option value="zh-CN">简体中文</Option>
                        <Option value="en-US">English</Option>
                      </Select>
                    </Form.Item>
                    <Button 
                      size="small" 
                      icon={<ReloadOutlined />}
                      onClick={() => resetConfigSection('preferences')}
                    >
                      重置为默认
                    </Button>
                  </div>
                ),
              },
            ]}
          />
        </Form>
      </Modal>

      {/* 预览配置弹窗 */}
      <Modal
        title={`预览配置：${selectedUser?.qq_user_id || selectedUser?.username}`}
        open={previewModalOpen}
        onCancel={() => setPreviewModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewModalOpen(false)}>
            关闭
          </Button>,
          <Button 
            key="copy" 
            icon={<CopyOutlined />}
            onClick={() => copyToClipboard(JSON.stringify(previewData, null, 2))}
          >
            复制JSON
          </Button>,
        ]}
        width={900}
      >
        {configLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>
        ) : (
          <pre style={{ 
            background: '#f5f5f5', 
            padding: 16, 
            borderRadius: 4, 
            overflow: 'auto',
            maxHeight: 500,
            fontSize: 12 
          }}>
            {JSON.stringify(previewData, null, 2)}
          </pre>
        )}
      </Modal>
    </div>
  )
}

export default AdminUsersPage
