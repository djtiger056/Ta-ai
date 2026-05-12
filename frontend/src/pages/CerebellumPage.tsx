import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Divider,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Row,
  Space,
  Statistic,
  Switch,
  Tag,
  Typography,
} from 'antd'
import {
  DashboardOutlined,
  HeartOutlined,
  ReloadOutlined,
  SaveOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'

import { cerebellumApi, proactiveApi } from '@/services/api'
import { proactiveConfigProxy } from '@/services/configProxy'
import { CerebellumHistoryItem, CerebellumMotivation, CerebellumState } from '@/types'

const { Title, Text } = Typography
const { TextArea } = Input
const { Panel } = Collapse

const EMOTION_META: Array<{ key: string; label: string; color: string }> = [
  { key: 'joy', label: '喜悦', color: '#ff8a3d' },
  { key: 'anger', label: '愤怒', color: '#e5484d' },
  { key: 'sadness', label: '悲伤', color: '#4c6fff' },
  { key: 'pleasure', label: '愉悦', color: '#ffb84d' },
  { key: 'surprise', label: '惊讶', color: '#00a6a6' },
  { key: 'fatigue', label: '疲倦', color: '#6b7280' },
]

const chartWidth = 720
const chartHeight = 240

const CerebellumPage: React.FC = () => {
  const [state, setState] = useState<CerebellumState | null>(null)
  const [motivations, setMotivations] = useState<CerebellumMotivation[]>([])
  const [history, setHistory] = useState<CerebellumHistoryItem[]>([])
  const [engineMeta, setEngineMeta] = useState<{ enabled: boolean; running: boolean; config?: any } | null>(null)
  const [loading, setLoading] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [configVisible, setConfigVisible] = useState(false)
  const [configLoading, setConfigLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [form] = Form.useForm()
  const wsRef = useRef<WebSocket | null>(null)

  const loadAll = async () => {
    try {
      setLoading(true)
      const [stateResp, motivationResp, historyResp] = await Promise.all([
        cerebellumApi.getState(),
        cerebellumApi.getMotivations(),
        cerebellumApi.getHistory(24, 240),
      ])
      setState(stateResp.state)
      setEngineMeta({ enabled: stateResp.enabled, running: stateResp.running, config: stateResp.config })
      setMotivations(motivationResp)
      setHistory(historyResp)
    } finally {
      setLoading(false)
    }
  }

  const loadProactiveConfig = async () => {
    try {
      const cfg = await proactiveConfigProxy.getConfig()
      form.setFieldsValue({
        default_prompt: cfg?.default_prompt || '',
        message_templates_text: (cfg?.message_templates || []).join('\n'),
        image_generation_enabled: cfg?.image_generation?.enabled ?? false,
        image_generation_max_per_day: cfg?.image_generation?.max_per_day ?? 3,
      })
    } catch (err) {
      console.error('加载主动消息配置失败', err)
    }
  }

  const handleSaveConfig = async () => {
    try {
      setConfigLoading(true)
      const values = await form.validateFields()
      const messageTemplates = (values.message_templates_text || '')
        .split('\n')
        .map((t: string) => t.trim())
        .filter(Boolean)
      
      await proactiveConfigProxy.updateConfig({
        default_prompt: values.default_prompt,
        message_templates: messageTemplates,
        image_generation: {
          enabled: values.image_generation_enabled,
          max_per_day: values.image_generation_max_per_day,
        },
      })
      message.success('配置已保存')
    } catch (err) {
      console.error(err)
      message.error('保存失败')
    } finally {
      setConfigLoading(false)
    }
  }

  const handleTrigger = async () => {
    try {
      setTriggering(true)
      const reply = await proactiveApi.triggerOnce({
        channel: 'web',
        user_id: 'web_user',
        session_id: 'web_user',
        display_name: '',
      })
      message.success(`已触发主动消息：${reply}`)
    } catch (err: any) {
      console.error(err)
      message.error(err?.response?.data?.detail || '触发失败')
    } finally {
      setTriggering(false)
    }
  }

  useEffect(() => {
    loadAll()
    loadProactiveConfig()
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let isMounted = true

    const connect = () => {
      if (!isMounted) return
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${protocol}://${window.location.host}/ws/cerebellum/stream`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload?.event !== 'cerebellum.state') {
            return
          }
          const nextState = payload?.payload?.state
          const nextMotivations = payload?.payload?.motivations
          if (nextState) {
            setState(nextState)
            setEngineMeta((prev) => ({
              enabled: payload?.payload?.enabled ?? prev?.enabled ?? false,
              running: payload?.payload?.running ?? prev?.running ?? false,
              config: prev?.config,
            }))
            setHistory((prev) => {
              const nextItem: CerebellumHistoryItem = {
                timestamp: nextState.last_updated_at,
                intensities: nextState.intensities,
                dominant_emotion: nextState.dominant_emotion,
                motivation_types: Array.isArray(nextMotivations) ? nextMotivations.map((item: any) => item.motivation_type) : [],
              }
              return [...prev.slice(-239), nextItem]
            })
          }
          if (Array.isArray(nextMotivations)) {
            setMotivations(nextMotivations)
          }
        } catch (error) {
          console.error('cerebellum ws parse failed', error)
        }
      }

      ws.onopen = () => {
        setWsConnected(true)
      }

      ws.onclose = () => {
        wsRef.current = null
        setWsConnected(false)
        if (isMounted) {
          reconnectTimer = setTimeout(connect, 5000)
        }
      }

      ws.onerror = () => {
        ws?.close()
      }
    }

    connect()

    return () => {
      isMounted = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
      wsRef.current = null
    }
  }, [])

  const trendLines = useMemo(() => {
    if (!history.length) {
      return []
    }
    return EMOTION_META.map((emotion) => {
      const points = history.map((item, index) => {
        const x = history.length === 1 ? 0 : (index / (history.length - 1)) * (chartWidth - 32)
        const y = (1 - Math.max(0, Math.min(1, Number(item.intensities?.[emotion.key] || 0)))) * (chartHeight - 32)
        return `${x + 16},${y + 16}`
      })
      return {
        ...emotion,
        points: points.join(' '),
      }
    })
  }, [history])

  const ringData = useMemo(() => {
    const values = EMOTION_META.map((emotion) => ({
      ...emotion,
      value: Number(state?.intensities?.[emotion.key] || 0),
    }))
    const total = values.reduce((sum, item) => sum + item.value, 0) || 1
    let start = 0
    return values.map((item) => {
      const ratio = item.value / total
      const end = start + ratio
      const itemWithAngles = { ...item, start, end }
      start = end
      return itemWithAngles
    })
  }, [state])

  const polarToCartesian = (cx: number, cy: number, r: number, angle: number) => {
    const radians = (angle - 90) * Math.PI / 180
    return {
      x: cx + r * Math.cos(radians),
      y: cy + r * Math.sin(radians),
    }
  }

  const describeArc = (start: number, end: number) => {
    const startAngle = start * 360
    const endAngle = end * 360
    const startPoint = polarToCartesian(110, 110, 78, endAngle)
    const endPoint = polarToCartesian(110, 110, 78, startAngle)
    const largeArcFlag = end - start > 0.5 ? 1 : 0
    return `M ${startPoint.x} ${startPoint.y} A 78 78 0 ${largeArcFlag} 0 ${endPoint.x} ${endPoint.y}`
  }

  return (
    <div className="cerebellum-page">
      <div className="cerebellum-hero">
        <div>
          <Title level={3} style={{ margin: 0, color: '#102a43' }}>
            情绪系统
          </Title>
          <Text style={{ color: '#486581' }}>
            实时观察 AI 的情绪流动、行为动机与昼夜节律。
          </Text>
        </div>
        <Space>
          <Switch
            checked={engineMeta?.enabled ?? false}
            loading={toggling}
            checkedChildren="已启用"
            unCheckedChildren="已关闭"
            onChange={async (checked) => {
              try {
                setToggling(true)
                const resp = await cerebellumApi.updateConfig({ enabled: checked })
                setEngineMeta((prev) => ({
                  ...prev,
                  enabled: resp?.config?.enabled ?? checked,
                  running: prev?.running ?? false,
                  config: resp?.config ?? prev?.config,
                }))
              } finally {
                setToggling(false)
              }
            }}
          />
          <Button 
            icon={<SettingOutlined />} 
            onClick={() => {
              setConfigVisible(!configVisible)
              if (!configVisible) loadProactiveConfig()
            }}
          >
            {configVisible ? '隐藏配置' : '主动消息配置'}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>
            刷新
          </Button>
          <Tag color={engineMeta?.running ? 'blue' : 'default'}>
            {engineMeta?.running ? '运行中' : '未运行'}
          </Tag>
          <Tag color={wsConnected ? 'cyan' : 'red'}>
            {wsConnected ? '实时连接' : '连接断开'}
          </Tag>
        </Space>
      </div>

      {!engineMeta?.enabled && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="情绪系统未启用"
          description="启用后，情绪和动机将持续驱动主动消息。点击上方开关即可启用。"
        />
      )}

      {configVisible && (
        <Card 
          title="主动消息配置" 
          style={{ marginBottom: 16 }}
          extra={
            <Space>
              <Button 
                icon={<ThunderboltOutlined />} 
                loading={triggering}
                onClick={handleTrigger}
              >
                立即触发
              </Button>
              <Button 
                type="primary" 
                icon={<SaveOutlined />} 
                loading={configLoading}
                onClick={handleSaveConfig}
              >
                保存配置
              </Button>
            </Space>
          }
        >
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="这些配置用于情绪系统触发主动消息时的提示词和行为"
            description="点击「立即触发」可以测试当前配置的效果，消息会发送到 Web 聊天页面"
          />
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              default_prompt: '',
              message_templates_text: '',
              image_generation_enabled: false,
              image_generation_max_per_day: 3,
            }}
          >
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item 
                  label="默认提示词" 
                  name="default_prompt"
                  tooltip="当情绪系统触发主动消息时使用的基础提示词"
                >
                  <TextArea 
                    rows={4} 
                    placeholder="例如：你突然想到他了，想发条消息给他..." 
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item 
                  label="话术模板（每行一条）" 
                  name="message_templates_text"
                  tooltip="可选的消息模板，系统会随机选择一条作为灵感参考"
                >
                  <TextArea 
                    rows={4} 
                    placeholder="今天过得怎么样呀？&#10;想你了，在干嘛呢？&#10;有没有想我呀~" 
                  />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item 
                  label="启用主动生图" 
                  name="image_generation_enabled" 
                  valuePropName="checked"
                  tooltip="允许AI在主动消息中生成图片"
                >
                  <Switch />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item 
                  label="每日生图上限" 
                  name="image_generation_max_per_day"
                  tooltip="每天最多生成的图片数量"
                >
                  <InputNumber min={0} max={10} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </Card>
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card className="cerebellum-card" bordered={false}>
            <div className="cerebellum-card-head">
              <Space>
                <HeartOutlined />
                <span>当前情绪分布</span>
              </Space>
              <Tag color="gold">{state?.dominant_emotion_label || '未初始化'}</Tag>
            </div>
            <div className="cerebellum-ring-wrap">
              <svg width="220" height="220" viewBox="0 0 220 220">
                <circle cx="110" cy="110" r="78" fill="none" stroke="#e6eef5" strokeWidth="22" />
                {ringData.map((item) => (
                  <path
                    key={item.key}
                    d={describeArc(item.start, item.end)}
                    fill="none"
                    stroke={item.color}
                    strokeWidth="22"
                    strokeLinecap="round"
                  />
                ))}
                <text x="110" y="102" textAnchor="middle" className="cerebellum-ring-title">
                  主导情绪
                </text>
                <text x="110" y="126" textAnchor="middle" className="cerebellum-ring-value">
                  {state?.dominant_emotion_label || '-'}
                </text>
              </svg>
              <div className="cerebellum-emotion-grid">
                {EMOTION_META.map((emotion) => (
                  <div key={emotion.key} className="cerebellum-emotion-item">
                    <span className="cerebellum-swatch" style={{ background: emotion.color }} />
                    <div style={{ flex: 1 }}>
                      <div className="cerebellum-emotion-label">{emotion.label}</div>
                      <div className="cerebellum-bar">
                        <span
                          className="cerebellum-bar-fill"
                          style={{
                            width: `${Math.round((Number(state?.intensities?.[emotion.key] || 0)) * 100)}%`,
                            background: emotion.color,
                          }}
                        />
                      </div>
                    </div>
                    <strong>{(Number(state?.intensities?.[emotion.key] || 0) * 100).toFixed(0)}%</strong>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Card className="cerebellum-stat" bordered={false}>
                <Statistic title="Tick间隔" value={engineMeta?.config?.tick_interval || 0} suffix="秒" />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="cerebellum-stat" bordered={false}>
                <Statistic title="衰减速率" value={engineMeta?.config?.decay_rate || 0} precision={3} />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="cerebellum-stat" bordered={false}>
                <Statistic title="动机阈值" value={engineMeta?.config?.action_threshold || 0} precision={2} />
              </Card>
            </Col>
            <Col xs={12} md={6}>
              <Card className="cerebellum-stat" bordered={false}>
                <Statistic title="Tick耗时" value={state?.last_tick_duration_ms || 0} precision={2} suffix="ms" />
              </Card>
            </Col>
          </Row>

          <Card className="cerebellum-card" bordered={false} style={{ marginTop: 16 }}>
            <div className="cerebellum-card-head">
              <Space>
                <ThunderboltOutlined />
                <span>当前动机</span>
              </Space>
            </div>
            {motivations.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有高强度动机信号" />
            ) : (
              <div className="cerebellum-motivation-list">
                {motivations.slice(-4).reverse().map((item) => (
                  <div key={`${item.motivation_type}-${item.created_at || Math.random()}`} className="cerebellum-motivation-item">
                    <div className="cerebellum-motivation-top">
                      <Space>
                        <Tag color={item.status === 'pending' ? 'orange' : item.status === 'dispatched' ? 'green' : 'blue'}>
                          {item.motivation_label}
                        </Tag>
                        <Text type="secondary">{item.dominant_emotion_label}</Text>
                      </Space>
                      <strong>{(item.intensity * 100).toFixed(0)}%</strong>
                    </div>
                    <div className="cerebellum-bar subtle">
                      <span
                        className="cerebellum-bar-fill"
                        style={{ width: `${Math.round(item.intensity * 100)}%`, background: '#2251ff' }}
                      />
                    </div>
                    <div className="cerebellum-motivation-desc">{item.description}</div>
                    <div className="cerebellum-motivation-time">
                      {item.created_at ? dayjs(item.created_at).format('MM-DD HH:mm:ss') : '刚刚'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="cerebellum-card" bordered={false} style={{ marginTop: 16 }}>
            <Descriptions title="状态摘要" column={1} size="small">
              <Descriptions.Item label="主导情绪">{state?.dominant_emotion_label || '-'}</Descriptions.Item>
              <Descriptions.Item label="最近激活情绪">{state?.last_triggered_emotion_label || '-'}</Descriptions.Item>
              <Descriptions.Item label="最近更新时间">
                {state?.last_updated_at ? dayjs(state.last_updated_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="历史长度">{history.length} 条</Descriptions.Item>
              <Descriptions.Item label="替代定时窗口">
                {engineMeta?.config?.replace_time_windows ? '已启用' : '未启用'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Card className="cerebellum-card" bordered={false} style={{ marginTop: 16 }}>
        <div className="cerebellum-card-head">
          <Space>
            <DashboardOutlined />
            <span>24小时情绪趋势</span>
          </Space>
        </div>
        {trendLines.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无趋势数据" />
        ) : (
          <>
            <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="cerebellum-trend">
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const y = 16 + ratio * (chartHeight - 32)
                return (
                  <g key={ratio}>
                    <line x1="16" y1={y} x2={chartWidth - 16} y2={y} stroke="#d9e2ec" strokeDasharray="4 4" />
                    <text x="4" y={y + 4} className="cerebellum-axis-label">
                      {(1 - ratio).toFixed(2)}
                    </text>
                  </g>
                )
              })}
              {trendLines.map((line) => (
                <polyline
                  key={line.key}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="3"
                  points={line.points}
                />
              ))}
            </svg>
            <div className="cerebellum-legend">
              {EMOTION_META.map((emotion) => (
                <span key={emotion.key} className="cerebellum-legend-item">
                  <span className="cerebellum-swatch" style={{ background: emotion.color }} />
                  {emotion.label}
                </span>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

export default CerebellumPage
