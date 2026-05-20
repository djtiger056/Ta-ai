import React, { useState, useEffect } from 'react';
import {
  Card, Form, Input, Button, message, Tabs, Switch,
  InputNumber, Select, Spin, Alert, Divider, Row, Col, Tag, Space,
} from 'antd';
import { SaveOutlined, ReloadOutlined, GlobalOutlined, FileTextOutlined, ToolOutlined } from '@ant-design/icons';
import axios from 'axios';

const { TextArea } = Input;
const { Option } = Select;

/**
 * 管理员全局配置页面
 * 配置系统默认值，用户未自定义时作为兜底。
 */
const AdminGlobalConfigPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [rawConfig, setRawConfig] = useState<any>(null);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/config');
      const cfg = response.data;
      setRawConfig(cfg);
      // 直接用嵌套结构填充表单
      form.setFieldsValue(cfg);
    } catch (error: any) {
      message.error('加载配置失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const deepMerge = (target: any, source: any): any => {
    const result = { ...(target ?? {}) };
    for (const key of Object.keys(source ?? {})) {
      if (source[key] !== null && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = deepMerge(target?.[key] ?? {}, source[key]);
      } else if (source[key] !== undefined) {
        result[key] = source[key];
      }
    }
    return result;
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const formValues = form.getFieldsValue();

      // 构建提交对象：只提交页面涉及的顶层字段
      const payload: any = {};

      if (formValues.llm) {
        payload.llm = deepMerge(rawConfig?.llm ?? {}, formValues.llm);
      }
      if (formValues.system_prompt !== undefined) {
        payload.system_prompt = formValues.system_prompt;
      }
      if (formValues.system_rules !== undefined) {
        payload.system_rules = formValues.system_rules;
      }
      if (formValues.adapters) {
        payload.adapters = deepMerge(rawConfig?.adapters ?? {}, formValues.adapters);
      }

      await axios.post('/api/config', payload);
      message.success('全局配置保存成功');
      loadConfig();
    } catch (error: any) {
      message.error('保存失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <Spin size="large" tip="加载配置中..." />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title={
          <span>
            <GlobalOutlined style={{ marginRight: 8 }} />
            全局默认配置
          </span>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadConfig}>刷新</Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
              保存全局配置
            </Button>
          </Space>
        }
      >
        <Alert
          message="全局配置说明"
          description="此处配置系统默认值。用户未自定义某项时将使用这里的值；用户自定义的配置优先级更高。"
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Form form={form} layout="vertical">
          <Tabs
            defaultActiveKey="llm"
            items={[
              // ── LLM ──────────────────────────────────────────────
              {
                key: 'llm',
                label: 'LLM 配置',
                children: (
                  <>
                    <Form.Item name={['llm', 'provider']} label="LLM 提供商">
                      <Select placeholder="选择 LLM 提供商">
                        <Option value="openai">OpenAI</Option>
                        <Option value="deepseek">DeepSeek</Option>
                        <Option value="qwen">通义千问</Option>
                        <Option value="siliconflow">SiliconFlow</Option>
                        <Option value="yunwu">Yunwu</Option>
                        <Option value="ollama">Ollama (本地)</Option>
                      </Select>
                    </Form.Item>
                    <Form.Item name={['llm', 'api_base']} label="API 地址">
                      <Input placeholder="https://api.openai.com/v1" />
                    </Form.Item>
                    <Form.Item name={['llm', 'api_key']} label="API Key">
                      <Input.Password placeholder="sk-..." />
                    </Form.Item>
                    <Form.Item name={['llm', 'model']} label="模型名称">
                      <Input placeholder="gpt-4o-mini" />
                    </Form.Item>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['llm', 'temperature']} label="Temperature">
                          <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['llm', 'max_tokens']} label="Max Tokens">
                          <InputNumber min={1} max={128000} style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                    </Row>
                  </>
                ),
              },

              // ── 系统提示词 ────────────────────────────────────────
              {
                key: 'prompt',
                label: '提示词',
                children: (
                  <Tabs
                    defaultActiveKey="persona"
                    size="small"
                    items={[
                      {
                        key: 'persona',
                        label: <span><FileTextOutlined /> 人设提示词</span>,
                        children: (
                          <>
                            <Alert
                              message="人设提示词（全局默认）"
                              description="定义 AI 的角色、性格、世界观、语言风格和行为准则。用户未自定义时使用此默认值。"
                              type="info"
                              showIcon
                              style={{ marginBottom: 16 }}
                            />
                            <Form.Item name="system_prompt" label="默认人设提示词">
                              <TextArea
                                rows={16}
                                placeholder="输入默认的人设提示词，用户未自定义时将使用此提示词"
                                style={{ fontFamily: 'monospace', fontSize: 13 }}
                              />
                            </Form.Item>
                          </>
                        ),
                      },
                      {
                        key: 'rules',
                        label: <span><ToolOutlined /> 功能协议</span>,
                        children: (
                          <>
                            <Alert
                              message="功能协议（全局默认）"
                              description={
                                <span>
                                  定义 AI 可使用的功能指令，如图片发送 <code>[GEN_IMG:]</code>、语音 <code>[TTS]</code>、任务委派 <code>[DELEGATE:]</code> 等。
                                  与人设分离，用户可独立覆盖。
                                </span>
                              }
                              type="info"
                              showIcon
                              style={{ marginBottom: 16 }}
                            />
                            <Form.Item name="system_rules" label="默认功能协议">
                              <TextArea
                                rows={16}
                                placeholder="输入默认的功能协议，留空则不注入任何功能协议"
                                style={{ fontFamily: 'monospace', fontSize: 13 }}
                              />
                            </Form.Item>
                          </>
                        ),
                      },
                    ]}
                  />
                ),
              },

              // ── 适配器 ────────────────────────────────────────────
              {
                key: 'adapters',
                label: '适配器',
                children: (
                  <>
                    <Alert
                      message="适配器决定机器人通过哪些渠道收发消息，修改后需重启后端服务才能生效。"
                      type="info"
                      showIcon
                      style={{ marginBottom: 20 }}
                    />

                    {/* 控制台 */}
                    <Card
                      size="small"
                      style={{ marginBottom: 16, borderRadius: 8 }}
                      title={<Space>🖥️ 控制台适配器 <Tag color="default">调试用</Tag></Space>}
                      extra={
                        <Form.Item name={['adapters', 'console', 'enabled']} valuePropName="checked" noStyle>
                          <Switch checkedChildren="已启用" unCheckedChildren="已禁用" />
                        </Form.Item>
                      }
                    >
                      <span style={{ color: '#888', fontSize: 13 }}>
                        在后端终端中直接输入消息与机器人对话，适合本地调试，无需额外配置。
                      </span>
                    </Card>

                    {/* QQ */}
                    <Card
                      size="small"
                      style={{ marginBottom: 16, borderRadius: 8 }}
                      title={<Space>🐧 QQ 适配器 <Tag color="blue">NapCat / OneBot</Tag></Space>}
                      extra={
                        <Form.Item name={['adapters', 'qq', 'enabled']} valuePropName="checked" noStyle>
                          <Switch checkedChildren="已启用" unCheckedChildren="已禁用" />
                        </Form.Item>
                      }
                    >
                      <Form.Item noStyle shouldUpdate={(p, c) =>
                        p?.adapters?.qq?.enabled !== c?.adapters?.qq?.enabled
                      }>
                        {({ getFieldValue }) => getFieldValue(['adapters', 'qq', 'enabled']) ? (
                          <>
                            <Divider  plain style={{ marginTop: 8 }}>连接配置</Divider>
                            <Row gutter={16}>
                              <Col span={16}>
                                <Form.Item name={['adapters', 'qq', 'ws_host']} label="WebSocket 地址">
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
                                    <InputNumber min={0.1} max={30} step={0.5} style={{ width: '100%' }} placeholder="最小 0.5" />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item name={['adapters', 'qq', 'segment_config', 'delay_range', 1]} noStyle>
                                    <InputNumber min={0.1} max={30} step={0.5} style={{ width: '100%' }} placeholder="最大 2.0" />
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
                          <span style={{ color: '#aaa', fontSize: 13 }}>启用后展开详细配置</span>
                        )}
                      </Form.Item>
                    </Card>

                    {/* Linyu */}
                    <Card
                      size="small"
                      style={{ marginBottom: 16, borderRadius: 8 }}
                      title={<Space>💬 Linyu 适配器 <Tag color="purple">Linyu IM</Tag></Space>}
                      extra={
                        <Form.Item name={['adapters', 'linyu', 'enabled']} valuePropName="checked" noStyle>
                          <Switch checkedChildren="已启用" unCheckedChildren="已禁用" />
                        </Form.Item>
                      }
                    >
                      <Form.Item noStyle shouldUpdate={(p, c) =>
                        p?.adapters?.linyu?.enabled !== c?.adapters?.linyu?.enabled
                      }>
                        {({ getFieldValue }) => getFieldValue(['adapters', 'linyu', 'enabled']) ? (
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
                                <Form.Item name={['adapters', 'linyu', 'http_host']} label="HTTP 地址">
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
                                    <InputNumber min={0.1} max={30} step={0.5} style={{ width: '100%' }} placeholder="最小 0.5" />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item name={['adapters', 'linyu', 'segment_config', 'delay_range', 1]} noStyle>
                                    <InputNumber min={0.1} max={30} step={0.5} style={{ width: '100%' }} placeholder="最大 2.0" />
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
                          <span style={{ color: '#aaa', fontSize: 13 }}>启用后展开详细配置</span>
                        )}
                      </Form.Item>
                    </Card>
                  </>
                ),
              },

              // ── TTS ───────────────────────────────────────────────
              {
                key: 'tts',
                label: 'TTS',
                children: (
                  <>
                    <Form.Item name={['tts', 'enabled']} label="启用 TTS" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name={['tts', 'provider']} label="TTS 提供商">
                      <Select placeholder="选择 TTS 提供商">
                        <Option value="edge">Edge TTS (免费)</Option>
                        <Option value="azure">Azure TTS</Option>
                        <Option value="openai">OpenAI TTS</Option>
                        <Option value="fish">Fish Audio</Option>
                        <Option value="qwen">通义千问 TTS</Option>
                      </Select>
                    </Form.Item>
                    <Alert
                      message="TTS 的详细配置（音色、语速等）请在左侧「TTS配置」页面设置"
                      type="info"
                      showIcon
                      style={{ marginTop: 16 }}
                    />
                  </>
                ),
              },

              // ── ASR ───────────────────────────────────────────────
              {
                key: 'asr',
                label: 'ASR',
                children: (
                  <>
                    <Form.Item name={['asr', 'enabled']} label="启用语音识别" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name={['asr', 'provider']} label="ASR 提供商">
                      <Select placeholder="选择 ASR 提供商">
                        <Option value="siliconflow">SiliconFlow</Option>
                        <Option value="qwen">通义千问 ASR</Option>
                        <Option value="assemblyai">AssemblyAI</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },

              // ── 图像生成 ──────────────────────────────────────────
              {
                key: 'image',
                label: '图像生成',
                children: (
                  <>
                    <Form.Item name={['image_generation', 'enabled']} label="启用图像生成" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name={['image_generation', 'provider']} label="图像生成提供商">
                      <Select placeholder="选择图像生成提供商">
                        <Option value="modelscope">ModelScope</Option>
                        <Option value="yunwu">Yunwu</Option>
                        <Option value="kling">Kling</Option>
                        <Option value="openai">OpenAI DALL-E</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },

              // ── 视觉识别 ──────────────────────────────────────────
              {
                key: 'vision',
                label: '视觉识别',
                children: (
                  <>
                    <Form.Item name={['vision', 'enabled']} label="启用视觉识别" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name={['vision', 'provider']} label="视觉识别提供商">
                      <Select placeholder="选择视觉识别提供商">
                        <Option value="openai">OpenAI Vision</Option>
                        <Option value="qwen">通义千问 VL</Option>
                        <Option value="modelscope">ModelScope</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },
            ]}
          />
        </Form>
      </Card>
    </div>
  );
};

export default AdminGlobalConfigPage;
