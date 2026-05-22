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
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Typography,
  message,
} from 'antd'
import { ExperimentOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { videoGenApi } from '@/services/api'
import { videoGenConfigProxy } from '@/services/configProxy'

const { Title, Text } = Typography

interface VideoGenConfig {
  enabled: boolean
  provider: string
  video_api: {
    api_base: string
    api_key: string
    provider: string
    model: string
    timeout: number
    ratio: string
    resolution: string
    duration: number
    use_async: boolean
    poll_interval: number
  }
  trigger_keywords: string[]
  prompt_instruction: string
  generating_message: string
  error_message: string
  success_message: string
}

const defaultConfig: VideoGenConfig = {
  enabled: false,
  provider: 'video_api',
  video_api: {
    api_base: 'http://127.0.0.1:18080',
    api_key: '',
    provider: 'qwen',
    model: 'wan2.7-t2v',
    timeout: 600,
    ratio: '16:9',
    resolution: '1080P',
    duration: 5,
    use_async: false,
    poll_interval: 4,
  },
  trigger_keywords: ['生成视频', '做个视频', '做一段视频', '视频生成', '文生视频'],
  prompt_instruction:
    '用户刚刚明确提出了视频生成需求。你可以把用户需求整理成一段适合视频生成模型的中文提示词。如果确实要生成视频，只输出自然回复，并在末尾附加一段 [GEN_VIDEO: 提示词]。提示词应包含主体、动作、场景、镜头、风格、光线和时长感。不要在用户没有主动要求生成视频时使用 [GEN_VIDEO:]。',
  generating_message: '🎬 正在为你生成视频，请稍候...',
  error_message: '😢 视频生成失败：{error}',
  success_message: '✨ 视频已生成完成！',
}

const modelOptions = [
  'wan2.7-t2v',
  'wan2.7-t2v-2026-04-25',
  'wan2.6-t2v',
  'qwen-happyhorse-1.0',
  'doubao-seedance-2.0-fast',
  'jimeng-video-3.5-pro',
  'jimeng-video-3.0-pro',
  'jimeng-video-seedance-2.0',
  'jimeng-video-seedance-2.0-fast',
]

const VideoGenPage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [testLoading, setTestLoading] = useState(false)
  const [generateLoading, setGenerateLoading] = useState(false)
  const [testVideoUrl, setTestVideoUrl] = useState<string | null>(null)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const data = await videoGenConfigProxy.getConfig()
      const merged = { ...defaultConfig, ...(data || {}), video_api: { ...defaultConfig.video_api, ...(data?.video_api || {}) } }
      form.setFieldsValue(merged)
    } catch (error) {
      message.error('加载配置失败')
      form.setFieldsValue(defaultConfig)
    } finally {
      setLoading(false)
    }
  }

  const saveConfig = async (values: VideoGenConfig) => {
    try {
      setLoading(true)
      await videoGenConfigProxy.updateConfig(values)
      message.success('配置保存成功')
    } catch (error) {
      message.error('配置保存失败')
    } finally {
      setLoading(false)
    }
  }

  const testConnection = async () => {
    try {
      setTestLoading(true)
      const success = await videoGenApi.testVideoGenConnection()
      if (success) message.success('连接测试成功')
      else message.error('连接测试失败')
    } catch (error) {
      message.error('连接测试失败')
    } finally {
      setTestLoading(false)
    }
  }

  const generateTestVideo = async () => {
    try {
      setGenerateLoading(true)
      setTestVideoUrl(null)
      const result = await videoGenApi.generateVideo('一只白猫在窗边缓慢回头看向镜头，晨光柔和，电影感镜头')
      if (result.success && result.video_url) {
        setTestVideoUrl(result.video_url)
        message.success('测试视频生成成功')
      } else {
        message.error(`视频生成失败：${result.message}`)
      }
    } catch (error) {
      message.error('视频生成失败')
    } finally {
      setGenerateLoading(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>
        <VideoCameraOutlined /> 视频生成配置
      </Title>

      <Row gutter={[24, 24]}>
        <Col span={16}>
          <Card title="基础配置" loading={loading}>
            <Form form={form} layout="vertical" initialValues={defaultConfig} onFinish={saveConfig}>
              <Form.Item name="enabled" label="启用视频生成" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Form.Item name="provider" label="提供商">
                <Select options={[{ value: 'video_api', label: 'Images API 视频服务' }]} />
              </Form.Item>

              <Divider>Images API 配置</Divider>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name={['video_api', 'api_base']} label="API 地址" rules={[{ required: true }]}>
                    <Input placeholder="http://127.0.0.1:18080" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name={['video_api', 'api_key']} label="API Key">
                    <Input.Password placeholder="未开启鉴权可留空" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name={['video_api', 'provider']} label="上游类型">
                    <Select
                      options={[
                        { value: 'qwen', label: 'Qwen / Wan' },
                        { value: 'doubao', label: 'Doubao Seedance' },
                        { value: 'jimeng', label: 'Jimeng' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name={['video_api', 'model']} label="模型">
                    <Select showSearch options={modelOptions.map(model => ({ value: model, label: model }))} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item name={['video_api', 'ratio']} label="比例">
                    <Select options={['16:9', '9:16', '1:1', '4:3', '3:4'].map(value => ({ value, label: value }))} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item name={['video_api', 'resolution']} label="清晰度">
                    <Select options={['720P', '1080P'].map(value => ({ value, label: value }))} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item name={['video_api', 'duration']} label="时长（秒）">
                    <InputNumber min={2} max={15} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item name={['video_api', 'timeout']} label="超时（秒）">
                    <InputNumber min={60} max={900} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name={['video_api', 'use_async']} label="使用异步任务" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name={['video_api', 'poll_interval']} label="轮询间隔（秒）">
                    <InputNumber min={1} max={10} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Divider>触发配置</Divider>
              <Form.Item name="trigger_keywords" label="语义关键词">
                <Select mode="tags" placeholder="输入关键词后回车" />
              </Form.Item>
              <Form.Item name="prompt_instruction" label="发给 AI 伴侣的可配置提示词">
                <Input.TextArea rows={6} />
              </Form.Item>
              <Form.Item name="generating_message" label="生成中消息">
                <Input />
              </Form.Item>
              <Form.Item name="error_message" label="错误消息">
                <Input />
              </Form.Item>
              <Form.Item name="success_message" label="成功消息">
                <Input />
              </Form.Item>

              <Space>
                <Button type="primary" htmlType="submit" loading={loading}>
                  保存配置
                </Button>
                <Button icon={<ExperimentOutlined />} onClick={testConnection} loading={testLoading}>
                  测试连接
                </Button>
              </Space>
            </Form>
          </Card>
        </Col>

        <Col span={8}>
          <Card title="测试功能">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Alert
                type="info"
                showIcon
                message="触发方式"
                description="用户主动提出生成视频时，系统才会把这里配置的提示词发给 AI 伴侣，让伴侣用 [GEN_VIDEO:] 返回视频提示词。"
              />
              <Button type="primary" onClick={generateTestVideo} loading={generateLoading} block>
                生成测试视频
              </Button>
              {generateLoading && (
                <div style={{ textAlign: 'center', padding: 20 }}>
                  <Spin size="large" />
                  <div style={{ marginTop: 10 }}>正在生成视频，请稍候...</div>
                </div>
              )}
              {testVideoUrl && (
                <div>
                  <Text strong>测试结果：</Text>
                  <video src={testVideoUrl} controls style={{ width: '100%', marginTop: 10, borderRadius: 8 }} />
                </div>
              )}
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default VideoGenPage
