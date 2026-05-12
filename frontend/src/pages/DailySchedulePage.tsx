import React, { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CalendarOutlined,
  CloudSyncOutlined,
  ReloadOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { dailyScheduleApi } from '@/services/api'
import {
  DailyScheduleGenConfig,
  GeneratedScheduleData,
  GeneratedScheduleSlot,
  GeneratedScheduleStatus,
} from '@/types'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

type DailyScheduleFormValues = DailyScheduleGenConfig & {
  use_custom_llm?: boolean
}

const defaultConfig: DailyScheduleGenConfig = {
  enabled: true,
  generate_window_start: '00:00',
  generate_window_end: '06:00',
  persona_name: '小馨',
  persona_desc: '温柔黏人的大三外语系女生，异地恋，校园生活，爱撒娇，偶尔小脾气',
  prompt_template: '',
  timezone: '',
  llm: null,
}

const DailySchedulePage: React.FC = () => {
  const [form] = Form.useForm<DailyScheduleFormValues>()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [status, setStatus] = useState<GeneratedScheduleStatus | null>(null)
  const [today, setToday] = useState<GeneratedScheduleData | null>(null)
  const useCustomLlm = Form.useWatch('use_custom_llm', form)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [cfg, stat] = await Promise.all([
        dailyScheduleApi.getConfig(),
        dailyScheduleApi.getStatus(),
      ])
      form.setFieldsValue({
        ...defaultConfig,
        ...cfg,
        use_custom_llm: !!cfg.llm,
        llm: cfg.llm || {
          provider: 'openai',
          api_base: '',
          api_key: '',
          model: '',
          temperature: 0.9,
          max_tokens: 2000,
        },
      })
      setStatus(stat)
      await loadToday(false)
    } catch (err) {
      console.error(err)
      message.error('加载每日作息生成配置失败')
    } finally {
      setLoading(false)
    }
  }

  const loadStatus = async () => {
    try {
      const stat = await dailyScheduleApi.getStatus()
      setStatus(stat)
    } catch (err) {
      console.error(err)
      setStatus(null)
    }
  }

  const loadToday = async (showError = true) => {
    try {
      const data = await dailyScheduleApi.getToday()
      setToday(data)
    } catch (err: any) {
      setToday(null)
      if (showError && err.response?.status !== 404) {
        message.error('读取今日作息失败')
      }
    }
  }

  const saveConfig = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const payload: DailyScheduleGenConfig = {
        enabled: values.enabled ?? true,
        generate_window_start: values.generate_window_start || '00:00',
        generate_window_end: values.generate_window_end || '06:00',
        persona_name: values.persona_name || defaultConfig.persona_name,
        persona_desc: values.persona_desc || defaultConfig.persona_desc,
        prompt_template: values.prompt_template || '',
        timezone: values.timezone || '',
        llm: values.use_custom_llm ? values.llm || {} : null,
      }
      await dailyScheduleApi.saveConfig(payload)
      message.success('每日作息生成配置已保存')
      await loadStatus()
    } catch (err) {
      console.error(err)
      message.error('保存失败，请检查表单内容')
    } finally {
      setSaving(false)
    }
  }

  const triggerGenerate = async (force = false) => {
    setGenerating(true)
    try {
      const result = await dailyScheduleApi.generate(force)
      if (result.success) {
        message.success(result.message)
      } else {
        message.info(result.message)
      }
      await Promise.all([loadStatus(), loadToday(false)])
    } catch (err: any) {
      console.error(err)
      message.error(err.response?.data?.detail || '生成失败，请检查 LLM 配置')
    } finally {
      setGenerating(false)
    }
  }

  const statusTag = () => {
    if (!status) return <Tag>未知</Tag>
    if (!status.config_enabled) return <Tag color="default">已禁用</Tag>
    if (status.generated) return <Tag color="green">已生成</Tag>
    return <Tag color="orange">今日未生成</Tag>
  }

  const columns = [
    {
      title: '时间',
      key: 'time',
      width: 160,
      render: (_: unknown, record: GeneratedScheduleSlot) => `${record.start} - ${record.end}`,
    },
    {
      title: '活动',
      dataIndex: 'activity',
      width: 180,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: '状态描述',
      dataIndex: 'desc',
      render: (value: string) => value || <Text type="secondary">暂无描述</Text>,
    },
  ]

  return (
    <div style={{ padding: '0 24px' }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            每日作息生成
          </Title>
          <Text type="secondary">用 LLM 每天生成一份有随机性的全天作息，并自动注入“你在干嘛”类回复上下文。</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>
              重新加载
            </Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={saveConfig} loading={saving}>
              保存配置
            </Button>
          </Space>
        </Col>
      </Row>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card
          title={
            <Space>
              <CalendarOutlined />
              <span>今日状态</span>
              {statusTag()}
            </Space>
          }
          loading={loading}
          extra={
            <Space>
              <Button
                icon={<ThunderboltOutlined />}
                onClick={() => triggerGenerate(false)}
                loading={generating}
              >
                手动生成
              </Button>
              <Popconfirm
                title="确认强制重新生成？"
                description="这会覆盖 data/generated_schedule.json 中今天的作息表。"
                okText="重新生成"
                cancelText="取消"
                onConfirm={() => triggerGenerate(true)}
              >
                <Button danger icon={<CloudSyncOutlined />} loading={generating}>
                  强制重生成
                </Button>
              </Popconfirm>
            </Space>
          }
        >
          <Row gutter={16}>
            <Col span={6}>
              <Text type="secondary">生成日期</Text>
              <Paragraph style={{ marginBottom: 0 }}>{status?.date || '暂无'}</Paragraph>
            </Col>
            <Col span={6}>
              <Text type="secondary">生成时间</Text>
              <Paragraph style={{ marginBottom: 0 }}>{status?.generated_at || '暂无'}</Paragraph>
            </Col>
            <Col span={6}>
              <Text type="secondary">时间段数量</Text>
              <Paragraph style={{ marginBottom: 0 }}>{status?.slot_count ?? 0}</Paragraph>
            </Col>
            <Col span={6}>
              <Text type="secondary">自动生成</Text>
              <Paragraph style={{ marginBottom: 0 }}>{status?.config_enabled ? '开启' : '关闭'}</Paragraph>
            </Col>
          </Row>
          {!today && (
            <Alert
              type="info"
              showIcon
              message="今天还没有可预览的生成作息。"
              description="可以等待凌晨窗口自动生成，也可以点击“手动生成”立即测试。"
              style={{ marginTop: 16 }}
            />
          )}
        </Card>

        {today && (
          <Card
            title="今日生成作息"
            extra={<Text type="secondary">来源：data/generated_schedule.json</Text>}
          >
            <Table
              rowKey={(record, index) => `${record.start}-${record.end}-${index}`}
              columns={columns}
              dataSource={today.slots || []}
              pagination={false}
              size="middle"
            />
          </Card>
        )}

        <Form form={form} layout="vertical" initialValues={defaultConfig}>
          <Card title="生成规则" loading={loading}>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name="enabled" label="启用自动生成" valuePropName="checked">
                  <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item
                  name="timezone"
                  label="时区"
                  tooltip="留空则使用主动聊天配置或 Asia/Shanghai"
                >
                  <Input placeholder="Asia/Shanghai" />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item
                  name="generate_window_start"
                  label="生成窗口开始"
                  rules={[{ required: true, message: '请输入开始时间' }]}
                >
                  <Input placeholder="00:00" />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item
                  name="generate_window_end"
                  label="生成窗口结束"
                  rules={[{ required: true, message: '请输入结束时间' }]}
                >
                  <Input placeholder="06:00" />
                </Form.Item>
              </Col>
            </Row>
            <Alert
              type="info"
              showIcon
              message="自动生成由后端 scheduler 每 60 秒检查一次。"
              description="只有当前时间落在生成窗口内、且今天尚未生成时才会调用 LLM；手动生成不受时间窗口限制。"
            />
          </Card>

          <Card title="人设注入" loading={loading}>
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name="persona_name" label="人设名称">
                  <Input placeholder="小馨" />
                </Form.Item>
              </Col>
              <Col span={16}>
                <Form.Item name="persona_desc" label="人设描述">
                  <Input placeholder="温柔黏人的大三外语系女生，异地恋，校园生活..." />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="prompt_template"
              label="自定义提示词模板"
              tooltip="留空使用后端内置模板。可使用 {weekday_cn}、{date_str}、{weekday_hint}、{persona_name}、{persona_desc}"
            >
              <TextArea
                rows={8}
                placeholder="留空则使用内置提示词模板。"
              />
            </Form.Item>
          </Card>

          <Card title="LLM 覆盖配置" loading={loading}>
            <Form.Item
              name="use_custom_llm"
              label="使用独立 LLM"
              valuePropName="checked"
              tooltip="关闭时复用全局 LLM 配置；开启时仅作息生成使用这里的模型。"
            >
              <Switch checkedChildren="独立" unCheckedChildren="复用全局" />
            </Form.Item>
            <Divider />
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name={['llm', 'provider']} label="提供商">
                  <Input disabled={!useCustomLlm} placeholder="openai / qwen / deepseek / siliconflow" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name={['llm', 'model']} label="模型">
                  <Input disabled={!useCustomLlm} placeholder="gpt-4o-mini" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name={['llm', 'api_base']} label="API 地址">
                  <Input disabled={!useCustomLlm} placeholder="https://api.openai.com/v1" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name={['llm', 'api_key']} label="API Key">
                  <Input.Password disabled={!useCustomLlm} placeholder="sk-..." />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name={['llm', 'temperature']} label="Temperature">
                  <InputNumber
                    disabled={!useCustomLlm}
                    min={0}
                    max={2}
                    step={0.1}
                    style={{ width: '100%' }}
                    placeholder="0.9"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name={['llm', 'max_tokens']} label="Max Tokens">
                  <InputNumber
                    disabled={!useCustomLlm}
                    min={500}
                    max={16000}
                    step={100}
                    style={{ width: '100%' }}
                    placeholder="2000"
                  />
                </Form.Item>
              </Col>
            </Row>
          </Card>
        </Form>
      </Space>
    </div>
  )
}

export default DailySchedulePage
