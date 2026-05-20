import React, { useState, useEffect } from 'react'
import { 
  Card, 
  Form, 
  Input, 
  InputNumber, 
  Switch, 
  Button, 
  message, 
  Tabs, 
  Space,
  Select,
  Divider,
  Row,
  Col,
  Alert,
  Tag,
} from 'antd'
import { SaveOutlined, ExperimentOutlined, CrownOutlined } from '@ant-design/icons'
import { SystemConfig } from '@/types'
import { configApi } from '@/services/api'
import { systemConfigProxy } from '@/services/configProxy'
import { useAuth } from '../contexts/AuthContext'

const { Option } = Select
const { TextArea } = Input

const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const currentProvider = Form.useWatch(['llm', 'provider'], form)
  const { isAdmin } = useAuth()

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      console.log('正在加载配置...')
      const data = await systemConfigProxy.getConfig()
      console.log('配置加载成功:', data)
      setConfig(data)
      form.setFieldsValue(data)
    } catch (error) {
      console.error('加载配置失败:', error)
      message.error('加载配置失败，请检查后端服务是否启动')
    }
  }

  const handleSave = async () => {
    try {
      setLoading(true)
      const formValues = form.getFieldsValue()
      
      // 深度合并：用表单值覆盖当前配置，保留未展示的嵌套字段
      const currentConfig = (config || {}) as any

      const deepMerge = (target: any, source: any): any => {
        const result = { ...target }
        for (const key of Object.keys(source ?? {})) {
          if (source[key] !== null && typeof source[key] === 'object' && !Array.isArray(source[key])) {
            result[key] = deepMerge(target?.[key] ?? {}, source[key])
          } else if (source[key] !== undefined) {
            result[key] = source[key]
          }
        }
        return result
      }

      const values = {
        llm: deepMerge(currentConfig.llm, formValues.llm),
        adapters: deepMerge(currentConfig.adapters, formValues.adapters),
        system_prompt: formValues.system_prompt ?? currentConfig.system_prompt,
      }
      
      await systemConfigProxy.updateConfig(values)
      message.success('配置保存成功')
      setConfig(values)
    } catch (error) {
      console.error('Save config error:', error)
      message.error('保存配置失败')
    } finally {
      setLoading(false)
    }
  }

  const handleTestLLM = async () => {
    try {
      setTesting(true)
      const success = await configApi.testLLMConnection()
      if (success) {
        message.success('LLM连接测试成功')
      } else {
        message.error('LLM连接测试失败')
      }
    } catch (error) {
      message.error('LLM连接测试失败')
    } finally {
      setTesting(false)
    }
  }

  const llmProviders = [
    { value: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
    { value: 'siliconflow', label: 'SiliconFlow', baseUrl: 'https://api.siliconflow.cn/v1' },
    { value: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1' },
    { value: 'yunwu', label: 'Yunwu', baseUrl: 'https://yunwu.ai/v1', alternatives: ['https://yunwu.ai', 'https://yunwu.ai/v1/chat/completions'] },
    { value: 'qwen', label: '千问（DashScope）', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ]

  const handleProviderChange = (provider: string) => {
    const selectedProvider = llmProviders.find(p => p.value === provider)
    if (selectedProvider) {
      form.setFieldsValue({
        llm: {
          api_base: selectedProvider.baseUrl
        }
      })
    }
  }

  return (
    <div>
      <Card title={
        <Space>
          <span>系统设置</span>
          {isAdmin ? (
            <Tag color="orange" icon={<CrownOutlined />}>管理员模式 - 修改将影响所有用户的默认配置</Tag>
          ) : (
            <Tag color="blue">个人模式 - 修改仅影响你自己</Tag>
          )}
        </Space>
      } extra={
        <Space>
          <Button 
            icon={<ExperimentOutlined />} 
            onClick={handleTestLLM}
            loading={testing}
          >
            测试LLM连接
          </Button>
          <Button 
            type="primary" 
            icon={<SaveOutlined />} 
            onClick={handleSave}
            loading={loading}
          >
            保存配置
          </Button>
        </Space>
      }>
        <Tabs defaultActiveKey="llm">
          <Tabs.TabPane tab="LLM配置" key="llm">
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                llm: {
                  temperature: 0.7,
                  max_tokens: 1000,
                }
              }}
            >
              <Form.Item
                label="LLM提供商"
                name={['llm', 'provider']}
                rules={[{ required: true, message: '请选择LLM提供商' }]}
              >
                <Select onChange={handleProviderChange}>
                  {llmProviders.map(provider => (
                    <Option key={provider.value} value={provider.value}>
                      {provider.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                label="模型"
                name={['llm', 'model']}
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input placeholder="例如: gpt-3.5-turbo, deepseek-ai/DeepSeek-V3, Yunwu模型名" />
              </Form.Item>

              <Form.Item
                label="API地址"
                name={['llm', 'api_base']}
                rules={[{ required: true, message: '请输入API地址' }]}
                help={
                  currentProvider === 'yunwu' 
                    ? '可尝试的BASE_URL：https://yunwu.ai 或 https://yunwu.ai/v1（部分客户端需使用 /v1/chat/completions）'
                    : undefined
                }
              >
                <Input placeholder={currentProvider === 'yunwu' ? 'https://yunwu.ai/v1' : 'https://api.openai.com/v1'} />
              </Form.Item>

              <Form.Item
                label="API密钥"
                name={['llm', 'api_key']}
                rules={[{ required: true, message: '请输入API密钥' }]}
              >
                <Input.Password placeholder="sk-..." />
              </Form.Item>

              <Form.Item
                label="温度"
                name={['llm', 'temperature']}
                help="控制回复的随机性，0-1之间，越高越随机"
              >
                <InputNumber
                  min={0}
                  max={1}
                  step={0.1}
                  precision={1}
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item
                label="最大Token数"
                name={['llm', 'max_tokens']}
                help="单次回复的最大字符数"
              >
                <InputNumber
                  min={100}
                  max={4000}
                  step={100}
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Form>
          </Tabs.TabPane>

          <Tabs.TabPane tab="适配器配置" key="adapters">
            <Form form={form} layout="vertical">
              <Alert
                message="适配器说明"
                description="适配器决定机器人通过哪些渠道收发消息。启用后需重启后端服务才能生效。可同时启用多个适配器。"
                type="info"
                showIcon
                style={{ marginBottom: 20 }}
              />

              {/* ── 控制台适配器 ── */}
              <Card
                size="small"
                style={{ marginBottom: 16, borderRadius: 8 }}
                title={
                  <Space>
                    <span>🖥️ 控制台适配器</span>
                    <Tag color="default">调试用</Tag>
                  </Space>
                }
                extra={
                  <Form.Item name={['adapters', 'console', 'enabled']} valuePropName="checked" noStyle>
                    <Switch checkedChildren="已启用" unCheckedChildren="已禁用" />
                  </Form.Item>
                }
              >
                <Alert
                  message="在后端终端中直接输入消息与机器人对话，适合本地调试。无需额外配置。"
                  type="info"
                  showIcon={false}
                  style={{ background: 'transparent', border: 'none', padding: 0 }}
                />
              </Card>

              {/* ── QQ 适配器 ── */}
              <Card
                size="small"
                style={{ marginBottom: 16, borderRadius: 8 }}
                title={
                  <Space>
                    <span>🐧 QQ 适配器</span>
                    <Tag color="blue">NapCat / OneBot</Tag>
                  </Space>
                }
                extra={
                  <Form.Item name={['adapters', 'qq', 'enabled']} valuePropName="checked" noStyle>
                    <Switch checkedChildren="已启用" unCheckedChildren="已禁用" />
                  </Form.Item>
                }
              >
                <Form.Item noStyle shouldUpdate={(prev, cur) =>
                  prev?.adapters?.qq?.enabled !== cur?.adapters?.qq?.enabled
                }>
                  {({ getFieldValue }) =>
                    getFieldValue(['adapters', 'qq', 'enabled']) ? (
                      <>
                        <Divider  plain style={{ marginTop: 8 }}>连接配置</Divider>
                        <Row gutter={16}>
                          <Col span={16}>
                            <Form.Item name={['adapters', 'qq', 'ws_host']} label="WebSocket 地址" help="NapCat 监听地址">
                              <Input placeholder="127.0.0.1" />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name={['adapters', 'qq', 'ws_port']} label="端口">
                              <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="3001" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Form.Item name={['adapters', 'qq', 'access_token']} label="访问令牌（可选）">
                          <Input.Password placeholder="留空表示不使用认证" />
                        </Form.Item>
                        <Form.Item
                          name={['adapters', 'qq', 'need_at']}
                          label="群聊需要 @ 机器人"
                          valuePropName="checked"
                          help="开启后群聊中必须 @ 机器人才会回复"
                        >
                          <Switch checkedChildren="需要" unCheckedChildren="不需要" />
                        </Form.Item>

                        <Divider  plain>分段发送</Divider>
                        <Form.Item
                          name={['adapters', 'qq', 'segment_config', 'enabled']}
                          label="启用分段发送"
                          valuePropName="checked"
                          help="将长消息拆分多段发送，模拟真人打字节奏"
                        >
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'qq', 'segment_config', 'max_segment_length']} label="每段最大长度">
                              <InputNumber min={10} max={500} step={10} style={{ width: '100%' }} placeholder="100" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'qq', 'segment_config', 'min_segment_length']} label="每段最小长度">
                              <InputNumber min={1} max={100} style={{ width: '100%' }} placeholder="5" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Form.Item label="段间延迟范围（秒）" help="每段之间的随机等待时间">
                          <Row gutter={16}>
                            <Col span={12}>
                              <Form.Item name={['adapters', 'qq', 'segment_config', 'delay_range', 0]} noStyle>
                                <InputNumber min={0.1} max={10} step={0.1} style={{ width: '100%' }} placeholder="最小 0.5" />
                              </Form.Item>
                            </Col>
                            <Col span={12}>
                              <Form.Item name={['adapters', 'qq', 'segment_config', 'delay_range', 1]} noStyle>
                                <InputNumber min={0.1} max={10} step={0.1} style={{ width: '100%' }} placeholder="最大 2.0" />
                              </Form.Item>
                            </Col>
                          </Row>
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'qq', 'segment_config', 'strategy']} label="分割策略">
                              <Select>
                                <Option value="sentence">按句子分段（更自然）</Option>
                                <Option value="length">按长度分段（更均匀）</Option>
                              </Select>
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'qq', 'segment_config', 'min_sentences_to_split']} label="最小句子数阈值">
                              <InputNumber min={1} max={10} style={{ width: '100%' }} placeholder="2" />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Divider  plain>消息防抖（合并）</Divider>
                        <Form.Item
                          name={['adapters', 'qq', 'debounce', 'enabled']}
                          label="启用消息防抖"
                          valuePropName="checked"
                          help="用户短时间内连续发送多条消息时，合并为一条后再回复，避免AI多次打断"
                        >
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item
                              name={['adapters', 'qq', 'debounce', 'delay']}
                              label="等待时间（秒）"
                              help="最后一条消息后等待多久再回复"
                            >
                              <InputNumber min={1} max={30} step={0.5} style={{ width: '100%' }} placeholder="3.0" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item
                              name={['adapters', 'qq', 'debounce', 'max_wait']}
                              label="最大等待时间（秒）"
                              help="防止用户一直打字导致永远不回复"
                            >
                              <InputNumber min={5} max={60} step={1} style={{ width: '100%' }} placeholder="15.0" />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    ) : (
                      <Alert message="启用后展开详细配置" type="warning" showIcon={false}
                        style={{ background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 6 }} />
                    )
                  }
                </Form.Item>
              </Card>

              {/* ── Linyu 适配器 ── */}
              <Card
                size="small"
                style={{ marginBottom: 16, borderRadius: 8 }}
                title={
                  <Space>
                    <span>💬 Linyu 适配器</span>
                    <Tag color="purple">Linyu IM</Tag>
                  </Space>
                }
                extra={
                  <Form.Item name={['adapters', 'linyu', 'enabled']} valuePropName="checked" noStyle>
                    <Switch checkedChildren="已启用" unCheckedChildren="已禁用" />
                  </Form.Item>
                }
              >
                <Form.Item noStyle shouldUpdate={(prev, cur) =>
                  prev?.adapters?.linyu?.enabled !== cur?.adapters?.linyu?.enabled
                }>
                  {({ getFieldValue }) =>
                    getFieldValue(['adapters', 'linyu', 'enabled']) ? (
                      <>
                        <Divider  plain style={{ marginTop: 8 }}>AI 账号配置</Divider>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'account']} label="AI 登录账号">
                              <Input placeholder="机器人登录账号" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'password']} label="密码">
                              <Input.Password placeholder="Linyu 登录密码" />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Divider  plain>服务器地址</Divider>
                        <Row gutter={16}>
                          <Col span={14}>
                            <Form.Item name={['adapters', 'linyu', 'http_host']} label="HTTP 地址" help="Linyu 服务器 IP 或域名">
                              <Input placeholder="127.0.0.1" />
                            </Form.Item>
                          </Col>
                          <Col span={10}>
                            <Form.Item name={['adapters', 'linyu', 'http_port']} label="HTTP 端口">
                              <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="9200" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Row gutter={16}>
                          <Col span={14}>
                            <Form.Item name={['adapters', 'linyu', 'ws_host']} label="WebSocket 地址">
                              <Input placeholder="127.0.0.1" />
                            </Form.Item>
                          </Col>
                          <Col span={10}>
                            <Form.Item name={['adapters', 'linyu', 'ws_port']} label="WebSocket 端口">
                              <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="9100" />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Divider  plain>聊天对象</Divider>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'target_user_id']} label="聊天对象 userId" help="这是 AI 要回复的用户，不是 AI 自己">
                              <Input placeholder="指定聊天对象的用户 ID" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'target_user_account']} label="聊天对象账号">
                              <Input placeholder="指定聊天对象的账号" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Form.Item
                          name={['adapters', 'linyu', 'auto_bind_first_user']}
                          label="自动绑定首个聊天对象"
                          valuePropName="checked"
                          help="适合单人测试；未手动指定聊天对象时，首次消息的发送者会被锁定为聊天对象"
                        >
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>

                        <Divider  plain>分段发送</Divider>
                        <Form.Item
                          name={['adapters', 'linyu', 'segment_config', 'enabled']}
                          label="启用分段发送"
                          valuePropName="checked"
                        >
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'segment_config', 'max_segment_length']} label="每段最大长度">
                              <InputNumber min={10} max={500} step={10} style={{ width: '100%' }} placeholder="100" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'segment_config', 'min_segment_length']} label="每段最小长度">
                              <InputNumber min={1} max={100} style={{ width: '100%' }} placeholder="5" />
                            </Form.Item>
                          </Col>
                        </Row>
                        <Form.Item label="段间延迟范围（秒）">
                          <Row gutter={16}>
                            <Col span={12}>
                              <Form.Item name={['adapters', 'linyu', 'segment_config', 'delay_range', 0]} noStyle>
                                <InputNumber min={0.1} max={10} step={0.1} style={{ width: '100%' }} placeholder="最小 0.5" />
                              </Form.Item>
                            </Col>
                            <Col span={12}>
                              <Form.Item name={['adapters', 'linyu', 'segment_config', 'delay_range', 1]} noStyle>
                                <InputNumber min={0.1} max={10} step={0.1} style={{ width: '100%' }} placeholder="最大 2.0" />
                              </Form.Item>
                            </Col>
                          </Row>
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'segment_config', 'strategy']} label="分割策略">
                              <Select>
                                <Option value="sentence">按句子分段（更自然）</Option>
                                <Option value="length">按长度分段（更均匀）</Option>
                              </Select>
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item name={['adapters', 'linyu', 'segment_config', 'min_sentences_to_split']} label="最小句子数阈值">
                              <InputNumber min={1} max={10} style={{ width: '100%' }} placeholder="2" />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Divider  plain>消息防抖（合并）</Divider>
                        <Form.Item
                          name={['adapters', 'linyu', 'debounce', 'enabled']}
                          label="启用消息防抖"
                          valuePropName="checked"
                          help="用户短时间内连续发送多条消息时，合并为一条后再回复，避免AI多次打断"
                        >
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Form.Item
                              name={['adapters', 'linyu', 'debounce', 'delay']}
                              label="等待时间（秒）"
                              help="最后一条消息后等待多久再回复"
                            >
                              <InputNumber min={1} max={30} step={0.5} style={{ width: '100%' }} placeholder="3.0" />
                            </Form.Item>
                          </Col>
                          <Col span={12}>
                            <Form.Item
                              name={['adapters', 'linyu', 'debounce', 'max_wait']}
                              label="最大等待时间（秒）"
                              help="防止用户一直打字导致永远不回复"
                            >
                              <InputNumber min={5} max={60} step={1} style={{ width: '100%' }} placeholder="15.0" />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    ) : (
                      <Alert message="启用后展开详细配置" type="warning" showIcon={false}
                        style={{ background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 6 }} />
                    )
                  }
                </Form.Item>
              </Card>
            </Form>
          </Tabs.TabPane>

          <Tabs.TabPane tab="系统提示词" key="prompt">
            <Form
              form={form}
              layout="vertical"
            >
              <Form.Item
                label="系统提示词"
                name="system_prompt"
                help="定义AI角色的提示词，影响机器人的性格和回复风格"
                rules={[{ required: true, message: '请输入系统提示词' }]}
              >
                <TextArea
                  rows={8}
                  placeholder="你是一个友好的AI助手..."
                />
              </Form.Item>
            </Form>
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </div>
  )
}

export default SettingsPage
