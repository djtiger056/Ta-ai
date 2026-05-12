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
      
      // 合并当前配置和表单值
      const currentConfig = (config || {}) as any
      const values = {
        llm: { ...currentConfig.llm, ...formValues.llm },
        adapters: { ...currentConfig.adapters, ...formValues.adapters },
        system_prompt: formValues.system_prompt || currentConfig.system_prompt
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
            <Form
              form={form}
              layout="vertical"
            >
              <Divider>控制台适配器</Divider>
              <Form.Item
                name={['adapters', 'console', 'enabled']}
                label="启用控制台适配器"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>

              <Divider>QQ适配器</Divider>
              <Form.Item
                name={['adapters', 'qq', 'enabled']}
                label="启用QQ适配器"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>

              <Form.Item
                name={['adapters', 'qq', 'ws_host']}
                label="WebSocket地址"
                help="NapCat WebSocket地址"
              >
                <Input placeholder="127.0.0.1" />
              </Form.Item>

              <Form.Item
                name={['adapters', 'qq', 'ws_port']}
                label="WebSocket端口"
                help="NapCat WebSocket端口"
              >
                <InputNumber min={1} max={65535} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item
                name={['adapters', 'qq', 'access_token']}
                label="访问令牌"
                help="访问令牌（可选）"
              >
                <Input placeholder="留空表示不使用认证" />
              </Form.Item>

              <Form.Item
                name={['adapters', 'qq', 'need_at']}
                label="需要@机器人"
                valuePropName="checked"
                help="群聊中是否需要@机器人才回复"
              >
                <Switch checkedChildren="需要" unCheckedChildren="不需要" />
              </Form.Item>

              <Divider>分段发送配置</Divider>
              
              <Form.Item
                name={['adapters', 'qq', 'segment_config', 'enabled']}
                label="启用分段发送"
                valuePropName="checked"
                help="将长消息分段发送，模拟真人聊天节奏"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name={['adapters', 'qq', 'segment_config', 'max_segment_length']}
                    label="每段最大长度"
                    help="超过此长度的消息会被分段"
                  >
                    <InputNumber 
                      min={10} 
                      max={500} 
                      step={10} 
                      style={{ width: '100%' }} 
                      placeholder="默认100" 
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['adapters', 'qq', 'segment_config', 'min_segment_length']}
                    label="每段最小长度"
                    help="低于此长度的段落不会被单独发送"
                  >
                    <InputNumber 
                      min={1} 
                      max={100} 
                      step={1} 
                      style={{ width: '100%' }} 
                      placeholder="默认5" 
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                label="段间延迟范围（秒）"
                help="每段消息发送之间的随机延迟，模拟真人输入"
              >
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['adapters', 'qq', 'segment_config', 'delay_range', 0]}
                      noStyle
                    >
                      <InputNumber 
                        min={0.1} 
                        max={10} 
                        step={0.1} 
                        style={{ width: '100%' }} 
                        placeholder="最小延迟，默认0.5" 
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['adapters', 'qq', 'segment_config', 'delay_range', 1]}
                      noStyle
                    >
                      <InputNumber 
                        min={0.1} 
                        max={10} 
                        step={0.1} 
                        style={{ width: '100%' }} 
                        placeholder="最大延迟，默认2.0" 
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Form.Item>

              <Form.Item
                name={['adapters', 'qq', 'segment_config', 'strategy']}
                label="分割策略"
                help="按句子分割（更自然）或按长度分割（更均匀）"
              >
                <Select placeholder="选择分割策略">
                  <Option value="sentence">按句子分段</Option>
                  <Option value="length">按长度分段</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name={['adapters', 'qq', 'segment_config', 'min_sentences_to_split']}
                label="最小句子数阈值"
                help="消息包含的句子数达到此阈值时，即使长度不长也会分段发送"
              >
                <InputNumber 
                  min={1} 
                  max={10} 
                  step={1} 
                  style={{ width: '100%' }} 
                  placeholder="默认2" 
                />
              </Form.Item>
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
