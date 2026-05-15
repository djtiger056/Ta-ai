import React, { useEffect, useMemo, useState } from 'react'
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
  Slider,
  Row,
  Col,
  Typography,
  Upload
} from 'antd'
import { ExperimentOutlined, PlayCircleOutlined, SaveOutlined } from '@ant-design/icons'
import { ASRConfig, TTSConfig, VoiceCharacter } from '@/types'
import { asrApi, ttsApi } from '@/services/api'
import { ttsConfigProxy, asrConfigProxy } from '@/services/configProxy'
import { useAuth } from '../contexts/AuthContext'

const { Option } = Select
const { Title, Text } = Typography

const siliconFlowModels = [
  'FunAudioLLM/SenseVoiceSmall',
  'TeleAI/TeleSpeechASR'
]

const qwenASRModels = [
  'qwen3-asr-flash',
  'qwen3-asr-plus'
]
const assemblyAIModels = [
  'universal-3-pro',
  'universal-2',
  'nano'
]


const TTSConfigPage: React.FC = () => {
  const [ttsForm] = Form.useForm<TTSConfig>()
  const [asrForm] = Form.useForm<ASRConfig>()

  const [ttsLoading, setTtsLoading] = useState(false)
  const [ttsSaving, setTtsSaving] = useState(false)
  const [ttsTesting, setTtsTesting] = useState(false)
  const [synthesizing, setSynthesizing] = useState(false)

  const [asrLoading, setAsrLoading] = useState(false)
  const [asrSaving, setAsrSaving] = useState(false)
  const [asrTesting, setAsrTesting] = useState(false)

  const [voices, setVoices] = useState<VoiceCharacter[]>([])
  const [audioUrl, setAudioUrl] = useState<string>('')
  const [customVoiceInput, setCustomVoiceInput] = useState('')
  const [qwenVoiceFile, setQwenVoiceFile] = useState<File | null>(null)
  const [qwenCloning, setQwenCloning] = useState(false)
  const [qwenAutoActivate, setQwenAutoActivate] = useState(true)

  const selectedProvider = Form.useWatch('provider', ttsForm)
  const selectedAsrProvider = Form.useWatch('provider', asrForm)
  const selectedVoice = Form.useWatch(['qihang', 'voice'], ttsForm)
  const qwenVoiceId = Form.useWatch(['qwen', 'voice_id'], ttsForm)
  const qwenSampleFile = Form.useWatch(['qwen', 'voice_sample_file'], ttsForm)
  const randomizationConfig = Form.useWatch('randomization', ttsForm)
  const randomizationTotal = useMemo(() => {
    const cfg: any = randomizationConfig || {}
    const full = Number(cfg?.full_probability ?? 0)
    const partial = Number(cfg?.partial_probability ?? 0)
    const none = Number(cfg?.none_probability ?? 0)
    return (full + partial + none).toFixed(2)
  }, [randomizationConfig])

  const voiceOptions = useMemo(() => {
    const list = [...voices]
    const candidates = [customVoiceInput, selectedVoice].filter(
      (name): name is string => !!name && !!name.trim()
    )

    candidates.forEach((name) => {
      if (!list.find((voice) => voice.name === name)) {
        list.unshift({ name, description: '自定义' })
      }
    })

    return list
  }, [voices, customVoiceInput, selectedVoice])

  useEffect(() => {
    loadTTSConfig()
    loadVoices()
    loadASRConfig()
  }, [])

  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
    }
  }, [audioUrl])

  const loadTTSConfig = async () => {
    try {
      setTtsLoading(true)
      const config = await ttsConfigProxy.getConfig()
      ttsForm.setFieldsValue(config)
    } catch (error) {
      message.error('加载 TTS 配置失败')
    } finally {
      setTtsLoading(false)
    }
  }

  const loadASRConfig = async () => {
    try {
      setAsrLoading(true)
      const config = await asrConfigProxy.getConfig()
      asrForm.setFieldsValue({
        ...config,
        provider: config?.provider || 'siliconflow',
        qwen: {
          api_base: config?.qwen?.api_base || 'https://dashscope.aliyuncs.com/compatible-mode/v1',
          api_key: config?.qwen?.api_key || '',
          model: config?.qwen?.model || 'qwen3-asr-flash',
          timeout: config?.qwen?.timeout || 30,
        },
        assemblyai: {
          api_base: config?.assemblyai?.api_base || 'https://api.assemblyai.com',
          api_key: config?.assemblyai?.api_key || '',
          model: config?.assemblyai?.model || 'universal-3-pro',
          timeout: config?.assemblyai?.timeout || 60,
        }
      })
    } catch (error) {
      message.error('加载 ASR 配置失败')
    } finally {
      setAsrLoading(false)
    }
  }

  const loadVoices = async () => {
    try {
      const voiceList = await ttsApi.getVoices()
      setVoices(voiceList)
    } catch (error) {
      message.error('加载语音角色列表失败')
    }
  }

  const handleSaveTTS = async () => {
    try {
      setTtsSaving(true)
      const values = await ttsForm.validateFields()
      if (values?.provider === 'qwen') {
        const apiKey = (values?.qwen?.api_key || '').trim()
        const voiceId = (values?.qwen?.voice_id || '').trim()
        if (!apiKey) {
          message.error('请先填写千问 API Key（DashScope）')
          return
        }
        if (!voiceId) {
          message.error('请先上传声音复刻音频并创建音色（voice_id）')
          return
        }
      }
      await ttsConfigProxy.updateConfig(values)
      message.success('TTS 配置已保存')
    } catch (error) {
      message.error('保存 TTS 配置失败')
    } finally {
      setTtsSaving(false)
    }
  }

  const handleTestTTSConnection = async () => {
    try {
      setTtsTesting(true)
      const success = await ttsApi.testTTSConnection()
      if (success) {
        message.success('TTS 连接测试成功')
      } else {
        message.error('TTS 连接测试失败')
      }
    } catch (error) {
      message.error('TTS 连接测试失败')
    } finally {
      setTtsTesting(false)
    }
  }

  const handleSynthesize = async () => {
    try {
      setSynthesizing(true)
      const testText = '你好，这是一个语音合成测试。'
      const provider = ttsForm.getFieldValue('provider')
      const voice = provider === 'qihang' ? ttsForm.getFieldValue(['qihang', 'voice']) : undefined
      const audioBlob = await ttsApi.synthesize(testText, voice)

      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
      const url = URL.createObjectURL(audioBlob)
      setAudioUrl(url)

      message.success('语音合成成功')
    } catch (error) {
      message.error('语音合成失败')
    } finally {
      setSynthesizing(false)
    }
  }

  const handleQwenVoiceClone = async () => {
    if (!qwenVoiceFile) {
      message.error('请先选择一段用于声音复刻的音频文件')
      return
    }

    try {
      setQwenCloning(true)
      const qwenCfg = (ttsForm.getFieldValue('qwen') || {}) as any
      const data = await ttsApi.qwenVoiceClone({
        file: qwenVoiceFile,
        activate: qwenAutoActivate,
        apiKey: qwenCfg.api_key,
        model: qwenCfg.model,
        preferredName: qwenCfg.preferred_name,
        customizationUrl: qwenCfg.customization_url,
        realtimeWsUrl: qwenCfg.realtime_ws_url,
      })

      ttsForm.setFieldsValue({
        ...(qwenAutoActivate ? { enabled: true, provider: 'qwen' } : {}),
        qwen: {
          ...(ttsForm.getFieldValue('qwen') as any),
          voice_id: data?.voice_id || '',
          voice_sample_file: data?.voice_sample_file || '',
        },
      } as any)

      message.success('声音复刻音色已创建/更新')
      setQwenVoiceFile(null)
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail ? `声音复刻失败：${detail}` : '声音复刻失败')
    } finally {
      setQwenCloning(false)
    }
  }

  const handleSaveASR = async () => {
    try {
      setAsrSaving(true)
      const values = await asrForm.validateFields()

      if (values?.provider === 'siliconflow') {
        const apiKey = (values?.siliconflow?.api_key || '').trim()
        if (!apiKey) {
          message.error('请先填写硅基流动 API 密钥')
          return
        }
      }

      if (values?.provider === 'qwen') {
        const apiKey = (values?.qwen?.api_key || '').trim()
        if (!apiKey) {
          message.error('请先填写千问 API Key（DashScope）')
          return
        }
      }

      if (values?.provider === 'assemblyai') {
        const apiKey = (values?.assemblyai?.api_key || '').trim()
        if (!apiKey) {
          message.error('请先填写 AssemblyAI API Key')
          return
        }
      }

      await asrConfigProxy.updateConfig(values)
      message.success('ASR 配置已保存')
    } catch (error) {
      message.error('保存 ASR 配置失败')
    } finally {
      setAsrSaving(false)
    }
  }

  const handleTestASRConnection = async () => {
    try {
      setAsrTesting(true)
      const success = await asrApi.testASRConnection()
      if (success) {
        message.success('ASR 连接正常')
      } else {
        message.error('ASR 连接测试失败')
      }
    } catch (error) {
      message.error('ASR 连接测试失败')
    } finally {
      setAsrTesting(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card
        title="TTS 语音合成配置"
        loading={ttsLoading}
        extra={
          <Space>
            <Button icon={<ExperimentOutlined />} onClick={handleTestTTSConnection} loading={ttsTesting}>
              测试连接
            </Button>
            <Button icon={<PlayCircleOutlined />} onClick={handleSynthesize} loading={synthesizing}>
              测试听例句
            </Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveTTS} loading={ttsSaving}>
              保存配置
            </Button>
          </Space>
        }
      >
        <Form form={ttsForm} layout="vertical">
          <Tabs defaultActiveKey="basic">
            <Tabs.TabPane tab="基础配置" key="basic">
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="enabled" label="启用 TTS" valuePropName="checked">
                    <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="probability"
                    label="触发概率"
                    help="每次回复触发 TTS 的概率，0-1 之间"
                  >
                    <Slider
                      min={0}
                      max={1}
                      step={0.1}
                      marks={{ 0: '0%', 0.5: '50%', 1: '100%' }}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="provider"
                label="TTS 提供商"
                help="启用“千问声音复刻”需要先上传音频创建音色（voice_id）"
              >
                <Select placeholder="选择提供商">
                  <Option value="qihang">启航 AI</Option>
                  <Option value="qwen">千问（声音复刻）</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="voice_only_when_tts"
                label="仅发送语音（隐藏文本）"
                valuePropName="checked"
                help="开启后，当生成了语音时不再发送对应的文本，仅发送语音消息（语音失败则回退文本）"
              >
                <Switch checkedChildren="仅语音" unCheckedChildren="文本+语音" />
              </Form.Item>

              <Form.Item
                name="proactive_enabled"
                label="允许AI主动触发TTS"
                valuePropName="checked"
                help="开启后，AI可以通过[TTS]标签主动决定哪些内容需要语音播报；关闭后AI的主动语音请求将被忽略"
              >
                <Switch checkedChildren="允许" unCheckedChildren="禁止" />
              </Form.Item>

              <Divider>随机播报</Divider>

              <Form.Item
                name={['randomization', 'enabled']}
                label="启用随机播报"
                valuePropName="checked"
                extra="随机决定播报完整内容、部分句子或静默，增加体验多样性"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item
                    name={['randomization', 'full_probability']}
                    label="完整播报概率"
                  >
                    <InputNumber
                      min={0}
                      max={1}
                      step={0.05}
                      style={{ width: '100%' }}
                      disabled={!randomizationConfig?.enabled}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name={['randomization', 'partial_probability']}
                    label="部分句子概率"
                  >
                    <InputNumber
                      min={0}
                      max={1}
                      step={0.05}
                      style={{ width: '100%' }}
                      disabled={!randomizationConfig?.enabled}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name={['randomization', 'none_probability']}
                    label="静默概率"
                  >
                    <InputNumber
                      min={0}
                      max={1}
                      step={0.05}
                      style={{ width: '100%' }}
                      disabled={!randomizationConfig?.enabled}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name={['randomization', 'min_partial_sentences']}
                    label="部分播报最少句数"
                  >
                    <InputNumber
                      min={1}
                      max={10}
                      step={1}
                      style={{ width: '100%' }}
                      disabled={!randomizationConfig?.enabled}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['randomization', 'max_partial_sentences']}
                    label="部分播报最多句数"
                  >
                    <InputNumber
                      min={1}
                      max={10}
                      step={1}
                      style={{ width: '100%' }}
                      disabled={!randomizationConfig?.enabled}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Text type="secondary">
                当前概率合计 {randomizationTotal}，超过 1 时会按权重自动归一化，设为 0 则保持默认完整播报。
              </Text>

              {selectedProvider !== 'qwen' && (
                <>
                  <Divider>启航 AI 配置</Divider>

                  <Form.Item
                    name={['qihang', 'api_base']}
                    label="API 地址"
                    rules={[{ required: true, message: '请输入 API 地址' }]}
                  >
                    <Input placeholder="https://api.qhaigc.net/v1" />
                  </Form.Item>

                  <Form.Item
                    name={['qihang', 'api_key']}
                    label="API 密钥"
                    rules={[{ required: true, message: '请输入 API 密钥' }]}
                  >
                    <Input.Password placeholder="请输入启航 AI API 密钥" />
                  </Form.Item>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name={['qihang', 'model']}
                        label="模型"
                        rules={[{ required: true, message: '请选择模型' }]}
                      >
                        <Select placeholder="选择模型">
                          <Option value="qhai-tts">qhai-tts</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name={['qihang', 'voice']}
                        label="语音角色"
                        rules={[{ required: true, message: '请选择语音角色' }]}
                      >
                        <Select
                          showSearch
                          allowClear
                          placeholder="选择或输入语音角色"
                          optionFilterProp="children"
                          onSearch={(value) => setCustomVoiceInput(value)}
                          onBlur={() => setCustomVoiceInput('')}
                          filterOption={(input, option) => {
                            const keyword = input.toLowerCase()
                            const valueText = (option?.value ?? '').toString().toLowerCase()
                            const labelText = option?.children?.toString().toLowerCase() ?? ''
                            return valueText.includes(keyword) || labelText.includes(keyword)
                          }}
                          notFoundContent="输入名称并回车即可使用自定义音色"
                        >
                          {voiceOptions.map((voice) => (
                            <Option key={voice.name} value={voice.name}>
                              {voice.name} {voice.description && `(${voice.description})`}
                            </Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              )}
            </Tabs.TabPane>

            <Tabs.TabPane tab="千问声音复刻" key="qwen">
              <Text type="secondary">
                支持直接上传本地音频（Base64 DataURI）创建音色，无需公网 URL。
              </Text>

              <Divider style={{ marginTop: 12 }}>基础参数</Divider>

              <Form.Item name={['qwen', 'api_key']} label="DashScope API Key">
                <Input.Password placeholder="填写 DashScope API Key（用于 CosyVoice/voice-enrollment）" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name={['qwen', 'model']} label="模型（target_model）" extra="声音复刻与语音合成必须使用同一个模型（推荐 qwen3-tts-vc-realtime-2025-11-27）">
                    <Input placeholder="qwen3-tts-vc-realtime-2025-11-27" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['qwen', 'preferred_name']}
                    label="音色名称（preferred_name）"
                    extra="用于创建音色的名称标识（例如：lfbot）"
                    rules={[
                      { required: true, message: '请输入音色名称' },
                      { pattern: /^[0-9A-Za-z_]{1,16}$/, message: '仅允许数字/字母/下划线，且不超过16字符' },
                    ]}
                  >
                    <Input placeholder="lfbot" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name={['qwen', 'customization_url']}
                    label="声音复刻接口地址（可选）"
                    extra="北京地域默认：https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
                  >
                    <Input placeholder="https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['qwen', 'realtime_ws_url']}
                    label="实时合成 WS 地址（可选）"
                    extra="北京地域默认：wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
                  >
                    <Input placeholder="wss://dashscope.aliyuncs.com/api-ws/v1/realtime" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name={['qwen', 'audio_format']} label="输出格式">
                    <Select placeholder="选择输出音频格式">
                      <Option value="mp3_44100">mp3_44100（推荐）</Option>
                      <Option value="mp3_24000">mp3_24000</Option>
                      <Option value="wav_24000">wav_24000</Option>
                      <Option value="wav_16000">wav_16000</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name={['qwen', 'timeout_millis']} label="合成超时（毫秒）">
                    <InputNumber min={3000} max={180000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name={['qwen', 'voice_id']} label="当前音色ID（voice_id）">
                    <Input readOnly placeholder="上传音频后自动生成/更新" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name={['qwen', 'voice_sample_file']} label="当前样本文件">
                    <Input readOnly placeholder="上传音频后自动填充" />
                  </Form.Item>
                </Col>
              </Row>

              <Divider>上传音频并复刻</Divider>

              <Form.Item label="上传后自动切换为千问TTS">
                <Switch
                  checked={qwenAutoActivate}
                  onChange={(checked) => setQwenAutoActivate(checked)}
                  checkedChildren="自动启用"
                  unCheckedChildren="仅创建音色"
                />
              </Form.Item>

              <Upload
                maxCount={1}
                beforeUpload={(file) => {
                  setQwenVoiceFile(file as any)
                  return false
                }}
                onRemove={() => {
                  setQwenVoiceFile(null)
                }}
                accept=".wav,.mp3,.m4a,.aac,.ogg"
              >
                <Button>选择声音复刻音频文件</Button>
              </Upload>

              <div style={{ marginTop: 12 }}>
                <Space>
                  <Button type="primary" loading={qwenCloning} onClick={handleQwenVoiceClone}>
                    上传并创建/更新音色
                  </Button>
                  <Text type="secondary">
                    {qwenVoiceFile ? `已选择：${qwenVoiceFile.name}` : '未选择文件'}
                  </Text>
                </Space>
              </div>

              {!!qwenVoiceId && (
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary">已配置音色ID：{qwenVoiceId}</Text>
                  {!!qwenSampleFile && (
                    <>
                      <br />
                      <Text type="secondary">样本文件：{qwenSampleFile}</Text>
                    </>
                  )}
                </div>
              )}
            </Tabs.TabPane>

            <Tabs.TabPane tab="分段配置" key="segment">
              <Form.Item
                name={['segment_config', 'enabled']}
                label="启用分段处理"
                valuePropName="checked"
                help="将长文本分段处理，提高合成效果"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name={['segment_config', 'strategy']} label="分段策略">
                    <Select>
                      <Option value="first">优先前段</Option>
                      <Option value="last">优先后段</Option>
                      <Option value="middle">优先中段</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['segment_config', 'max_segments']} label="最大段数">
                    <InputNumber min={1} max={5} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['segment_config', 'send_timing']} label="发送时机">
                    <Select>
                      <Option value="sync">同步</Option>
                      <Option value="async">异步</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name={['segment_config', 'min_segment_length']} label="最小分段长度">
                    <InputNumber min={1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['segment_config', 'max_segment_length']} label="最大分段长度">
                    <InputNumber min={10} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['segment_config', 'interval_step']} label="分段间隔（秒）">
                    <InputNumber min={1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="分段延迟范围（秒）">
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item name={['segment_config', 'delay_range', 0]} noStyle>
                      <InputNumber min={0} step={0.1} style={{ width: '100%' }} placeholder="最小延迟" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name={['segment_config', 'delay_range', 1]} noStyle>
                      <InputNumber min={0} step={0.1} style={{ width: '100%' }} placeholder="最大延迟" />
                    </Form.Item>
                  </Col>
                </Row>
              </Form.Item>
            </Tabs.TabPane>

            <Tabs.TabPane tab="文本清洗" key="cleaning">
              <Form.Item
                name={['text_cleaning', 'enabled']}
                label="启用文本清洗"
                valuePropName="checked"
                help="清洗不适合语音朗读的内容，避免异常朗读"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name={['text_cleaning', 'remove_emoji']} label="移除 Emoji" valuePropName="checked">
                    <Switch checkedChildren="是" unCheckedChildren="否" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['text_cleaning', 'remove_kaomoji']} label="移除颜文字" valuePropName="checked">
                    <Switch checkedChildren="是" unCheckedChildren="否" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name={['text_cleaning', 'remove_action_text']}
                    label="移除动作描述"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="是" unCheckedChildren="否" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item
                    name={['text_cleaning', 'remove_brackets_content']}
                    label="移除括号内容"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="是" unCheckedChildren="否" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name={['text_cleaning', 'remove_markdown']}
                    label="移除 Markdown"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="是" unCheckedChildren="否" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['text_cleaning', 'max_length']} label="最大文本长度">
                    <InputNumber min={10} max={1000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Tabs.TabPane>
          </Tabs>
        </Form>

        {audioUrl && (
          <div style={{ marginTop: 24 }}>
            <Title level={4}>语音测试结果</Title>
            <audio controls style={{ width: '100%' }}>
              <source src={audioUrl} />
              您的浏览器不支持音频播放
            </audio>
          </div>
        )}
      </Card>

      <Card
        title="ASR 语音识别配置"
        loading={asrLoading}
        extra={
          <Space>
            <Button icon={<ExperimentOutlined />} onClick={handleTestASRConnection} loading={asrTesting}>
              测试连接
            </Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveASR} loading={asrSaving}>
              保存配置
            </Button>
          </Space>
        }
      >
        <Form form={asrForm} layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="enabled" label="启用 ASR" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="auto_send_to_llm"
                label="自动发送识别结果到 LLM"
                valuePropName="checked"
              >
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="provider"
                label="提供商"
                rules={[{ required: true, message: '请选择 ASR 提供商' }]}
              >
                <Select>
                  <Option value="siliconflow">硅基流动</Option>
                  <Option value="qwen">千问（DashScope）</Option>
                  <Option value="assemblyai">AssemblyAI</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="processing_message" label="处理中提示语">
                <Input placeholder="正在识别语音..." />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="error_message" label="错误提示语">
                <Input placeholder="语音识别失败了呢" />
              </Form.Item>
            </Col>
          </Row>

          {selectedAsrProvider === 'siliconflow' && (
            <>
              <Divider>硅基流动配置</Divider>

              <Form.Item
                name={['siliconflow', 'api_base']}
                label="API 地址"
                rules={[{ required: true, message: '请输入 API 地址' }]}
              >
                <Input placeholder="https://api.siliconflow.cn/v1" />
              </Form.Item>

              <Form.Item
                name={['siliconflow', 'api_key']}
                label="API 密钥"
                rules={[{ required: true, message: '请输入 API 密钥' }]}
              >
                <Input.Password placeholder="请输入硅基流动 API 密钥" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name={['siliconflow', 'model']}
                    label="模型"
                    rules={[{ required: true, message: '请选择模型' }]}
                  >
                    <Select
                      showSearch
                      placeholder="例：FunAudioLLM/SenseVoiceSmall"
                      optionFilterProp="children"
                    >
                      {siliconFlowModels.map((model) => (
                        <Option value={model} key={model}>
                          {model}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['siliconflow', 'timeout']}
                    label="超时时间（秒）"
                  >
                    <InputNumber min={5} max={180} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}

          {selectedAsrProvider === 'qwen' && (
            <>
              <Divider>千问 ASR 配置（DashScope）</Divider>
              <Form.Item
                name={['qwen', 'api_base']}
                label="API 地址"
                extra="默认使用 OpenAI 兼容地址（北京地域）"
                rules={[{ required: true, message: '请输入 API 地址' }]}
              >
                <Input placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
              </Form.Item>
              <Form.Item
                name={['qwen', 'api_key']}
                label="API 密钥"
                rules={[{ required: true, message: '请输入 API 密钥' }]}
              >
                <Input.Password placeholder="请输入千问 DashScope API Key" />
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name={['qwen', 'model']}
                    label="模型"
                    rules={[{ required: true, message: '请选择模型' }]}
                  >
                    <Select showSearch placeholder="例：qwen3-asr-flash" optionFilterProp="children">
                      {qwenASRModels.map((model) => (
                        <Option value={model} key={model}>
                          {model}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['qwen', 'timeout']}
                    label="超时时间（秒）"
                  >
                    <InputNumber min={5} max={180} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}

          {selectedAsrProvider === 'assemblyai' && (
            <>
              <Divider>AssemblyAI 配置</Divider>

              <Form.Item
                name={['assemblyai', 'api_base']}
                label="API 地址"
                extra="默认使用官方地址；如有代理可自行修改"
                rules={[{ required: true, message: '请输入 API 地址' }]}
              >
                <Input placeholder="https://api.assemblyai.com" />
              </Form.Item>

              <Form.Item
                name={['assemblyai', 'api_key']}
                label="API 密钥"
                rules={[{ required: true, message: '请输入 API 密钥' }]}
              >
                <Input.Password placeholder="请输入 AssemblyAI API Key" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name={['assemblyai', 'model']}
                    label="模型"
                    rules={[{ required: true, message: '请选择模型' }]}
                  >
                    <Select showSearch placeholder="例：universal-3-pro" optionFilterProp="children">
                      {assemblyAIModels.map((model) => (
                        <Option value={model} key={model}>
                          {model}
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name={['assemblyai', 'timeout']}
                    label="超时时间（秒）"
                    extra="AssemblyAI 为异步转录，建议设大一些（30-120秒）"
                  >
                    <InputNumber min={10} max={300} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}
        </Form>
      </Card>
    </div>
  )
}

export default TTSConfigPage
