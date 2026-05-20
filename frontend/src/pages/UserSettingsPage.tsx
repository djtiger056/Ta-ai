import React, { useState, useEffect } from 'react';
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
  Alert,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
  Divider,
  Row,
  Col,
} from 'antd';
import { 
  SaveOutlined, 
  ExperimentOutlined, 
  ReloadOutlined,
  InfoCircleOutlined,
  DeleteOutlined,
  QqOutlined,
  LinkOutlined,
  FileTextOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { userConfigApi, configApi, authApi, promptApi } from '@/services/api';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const { Option } = Select;
const { TextArea } = Input;

/**
 * QQ 绑定区域组件
 */
const QQBindSection: React.FC<{ user: any; onSuccess: () => void }> = ({ user, onSuccess }) => {
  const [qqId, setQqId] = useState('');
  const [binding, setBinding] = useState(false);
  const { refreshUser } = useAuth();

  const handleBind = async () => {
    if (!qqId.trim()) {
      message.warning('请输入 QQ 号');
      return;
    }
    if (!/^\d{5,12}$/.test(qqId.trim())) {
      message.warning('请输入有效的 QQ 号（5-12位数字）');
      return;
    }
    setBinding(true);
    try {
      await authApi.bindQQ(qqId.trim());
      message.success('QQ 号绑定成功');
      setQqId('');
      await refreshUser();
      onSuccess();
    } catch (error: any) {
      const detail = error.response?.data?.detail || error.message;
      message.error('绑定失败: ' + detail);
    } finally {
      setBinding(false);
    }
  };

  return (
    <>
      <Alert
        message="QQ 号绑定"
        description="绑定 QQ 号后，通过 QQ 聊天时系统能识别你的身份，自动使用你上传的底图进行图生图。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      {user?.qq_user_id ? (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <QqOutlined style={{ fontSize: 20, color: '#1890ff' }} />
            <span>当前绑定的 QQ 号：</span>
            <Tag color="blue" style={{ fontSize: 14 }}>{user.qq_user_id}</Tag>
          </Space>
        </div>
      ) : (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <QqOutlined style={{ fontSize: 20, color: '#999' }} />
            <span style={{ color: '#999' }}>尚未绑定 QQ 号</span>
          </Space>
        </div>
      )}

      <Form.Item label="绑定新的 QQ 号" help="输入你的 QQ 号并点击绑定，每个 QQ 号只能绑定一个账号">
        <Space>
          <Input
            placeholder="输入 QQ 号"
            value={qqId}
            onChange={(e) => setQqId(e.target.value)}
            style={{ width: 200 }}
            prefix={<QqOutlined />}
            onPressEnter={handleBind}
          />
          <Button
            type="primary"
            icon={<LinkOutlined />}
            onClick={handleBind}
            loading={binding}
          >
            绑定
          </Button>
        </Space>
      </Form.Item>
    </>
  );
};

/**
 * Linyu 绑定区域组件
 */
const LinyuBindSection: React.FC<{ user: any; onSuccess: () => void }> = ({ user, onSuccess }) => {
  const [linyuId, setLinyuId] = useState('');
  const [binding, setBinding] = useState(false);
  const { refreshUser } = useAuth();

  const handleBind = async () => {
    if (!linyuId.trim()) {
      message.warning('请输入 Linyu 账号');
      return;
    }
    setBinding(true);
    try {
      await authApi.bindLinyu(linyuId.trim());
      message.success('Linyu 账号绑定成功');
      setLinyuId('');
      await refreshUser();
      onSuccess();
    } catch (error: any) {
      const detail = error.response?.data?.detail || error.message;
      message.error('绑定失败: ' + detail);
    } finally {
      setBinding(false);
    }
  };

  return (
    <>
      <Alert
        message="Linyu 账号绑定"
        description="这里绑定的是你的 Linyu 用户账号（身份），不是 AI 登录账号。AI 机器人账号由管理员在全局 Linyu 适配器里配置。你可以输入账号名或用户 ID。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      {user?.linyu_user_id ? (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <LinkOutlined style={{ fontSize: 20, color: '#722ed1' }} />
            <span>当前绑定的 Linyu 用户账号：</span>
            <Tag color="purple" style={{ fontSize: 14 }}>{user.linyu_account || user.linyu_user_id}</Tag>
          </Space>
        </div>
      ) : (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <LinkOutlined style={{ fontSize: 20, color: '#999' }} />
            <span style={{ color: '#999' }}>尚未绑定 Linyu 账号</span>
          </Space>
        </div>
      )}

      <Form.Item label="绑定你的 Linyu 账号" help="输入你的用户账号名或用户 ID，系统会自动解析。每个 Linyu 用户账号只能绑定一个用户">
        <Space>
          <Input
            placeholder="输入 Linyu 账号名或用户 ID"
            value={linyuId}
            onChange={(e) => setLinyuId(e.target.value)}
            style={{ width: 240 }}
            prefix={<LinkOutlined />}
            onPressEnter={handleBind}
          />
          <Button
            type="primary"
            icon={<LinkOutlined />}
            onClick={handleBind}
            loading={binding}
          >
            绑定
          </Button>
        </Space>
      </Form.Item>
    </>
  );
};

/**
 * 用户个人设置页面
 * 用户可以在这里配置自己的个性化设置，覆盖全局默认配置
 */
const UserSettingsPage: React.FC = () => {
  const [form] = Form.useForm();
  const [adapterForm] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingAdapters, setSavingAdapters] = useState(false);
  const [testing, setTesting] = useState(false);
  const [userConfig, setUserConfig] = useState<any>(null);
  const [globalConfig, setGlobalConfig] = useState<any>(null);
  // 提示词系统状态
  const [promptContent, setPromptContent] = useState('');
  const [promptIsCustom, setPromptIsCustom] = useState(false);
  const [defaultPrompt, setDefaultPrompt] = useState('');
  const [rulesContent, setRulesContent] = useState('');
  const [rulesIsCustom, setRulesIsCustom] = useState(false);
  const [defaultRules, setDefaultRules] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [savingRules, setSavingRules] = useState(false);
  const { user, isAdmin } = useAuth();

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      // 并行加载用户配置、全局配置、提示词系统
      const [userCfg, globalCfg, promptData, rulesData, defPrompt, defRules] = await Promise.all([
        userConfigApi.getConfig(),
        configApi.getConfig(),
        promptApi.getPrompt(),
        promptApi.getRules(),
        promptApi.getDefaultPrompt(),
        promptApi.getDefaultRules(),
      ]);
      
      setUserConfig(userCfg);
      setGlobalConfig(globalCfg);
      setPromptContent(promptData.content);
      setPromptIsCustom(promptData.is_custom);
      setDefaultPrompt(defPrompt);
      setRulesContent(rulesData.content);
      setRulesIsCustom(rulesData.is_custom);
      setDefaultRules(defRules);
      
      // 设置表单值（LLM / TTS / 用户级适配器）
      form.setFieldsValue({
        llm: userCfg.llm || {},
        tts: userCfg.tts || {},
        adapters: userCfg.adapters || {},
      });

      // 管理员：加载适配器配置到 adapterForm
      if (globalCfg?.adapters) {
        adapterForm.setFieldsValue(globalCfg);
      }
    } catch (error: any) {
      message.error('加载配置失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const values = form.getFieldsValue();
      
      // 保存 LLM / TTS / 用户级适配器配置
      const updateData: any = {};
      
      if (values.llm && Object.keys(values.llm).some(k => values.llm[k])) {
        updateData.llm = values.llm;
      }
      
      if (values.tts && Object.keys(values.tts).some(k => values.tts[k])) {
        updateData.tts = values.tts;
      }

      if (values.adapters?.linyu && Object.keys(values.adapters.linyu).some(k => values.adapters.linyu[k] !== undefined && values.adapters.linyu[k] !== '')) {
        const rawLinyu = values.adapters.linyu || {};
        const sanitizedLinyu = {
          enabled: rawLinyu.enabled,
          auto_bind_first_user: rawLinyu.auto_bind_first_user,
          account: rawLinyu.account,
          password: rawLinyu.password,
        };
        updateData.adapters = {
          linyu: sanitizedLinyu,
        };
      }
      
      await userConfigApi.updateConfig(updateData);
      message.success('配置保存成功');
      loadConfigs();
    } catch (error: any) {
      message.error('保存失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSaving(false);
    }
  };

  const handleSavePrompt = async () => {
    if (!promptContent.trim()) {
      message.warning('提示词内容不能为空');
      return;
    }
    setSavingPrompt(true);
    try {
      await promptApi.updatePrompt(promptContent);
      message.success('人设提示词已保存');
      setPromptIsCustom(true);
    } catch (error: any) {
      message.error('保存失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSavingPrompt(false);
    }
  };

  const handleResetPrompt = async () => {
    try {
      await promptApi.resetPrompt();
      const defPrompt = await promptApi.getDefaultPrompt();
      setPromptContent(defPrompt);
      setPromptIsCustom(false);
      message.success('已重置为全局默认人设');
    } catch (error: any) {
      message.error('重置失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleSaveRules = async () => {
    setSavingRules(true);
    try {
      await promptApi.updateRules(rulesContent);
      message.success('功能协议已保存');
      setRulesIsCustom(true);
    } catch (error: any) {
      message.error('保存失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSavingRules(false);
    }
  };

  const handleResetRules = async () => {
    try {
      await promptApi.resetRules();
      const defRules = await promptApi.getDefaultRules();
      setRulesContent(defRules);
      setRulesIsCustom(false);
      message.success('已重置为全局默认功能协议');
    } catch (error: any) {
      message.error('重置失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleReset = async (configType?: string) => {
    try {
      await userConfigApi.resetConfig(configType);
      message.success(configType ? `${configType} 配置已重置` : '所有配置已重置');
      loadConfigs();
    } catch (error: any) {
      message.error('重置失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleSaveAdapters = async () => {
    setSavingAdapters(true);
    try {
      const formValues = adapterForm.getFieldsValue();
      const deepMerge = (target: any, source: any): any => {
        const result = { ...target };
        for (const key of Object.keys(source ?? {})) {
          if (source[key] !== null && typeof source[key] === 'object' && !Array.isArray(source[key])) {
            result[key] = deepMerge(target?.[key] ?? {}, source[key]);
          } else if (source[key] !== undefined) {
            result[key] = source[key];
          }
        }
        return result;
      };
      const payload = {
        adapters: deepMerge(globalConfig?.adapters ?? {}, formValues.adapters),
      };
      await axios.post('/api/config', payload);
      message.success('适配器配置保存成功，重启后端后生效');
      loadConfigs();
    } catch (error: any) {
      message.error('保存失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSavingAdapters(false);
    }
  };

  const handleTestLLM = async () => {
    setTesting(true);
    try {
      const success = await configApi.testLLMConnection();
      if (success) {
        message.success('LLM 连接测试成功');
      } else {
        message.error('LLM 连接测试失败');
      }
    } catch (error) {
      message.error('LLM 连接测试失败');
    } finally {
      setTesting(false);
    }
  };

  const llmProviders = [
    { value: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
    { value: 'siliconflow', label: 'SiliconFlow', baseUrl: 'https://api.siliconflow.cn/v1' },
    { value: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1' },
    { value: 'yunwu', label: 'Yunwu', baseUrl: 'https://yunwu.ai/v1' },
    { value: 'qwen', label: '千问（DashScope）', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  ];

  const handleProviderChange = (provider: string) => {
    const selectedProvider = llmProviders.find(p => p.value === provider);
    if (selectedProvider) {
      form.setFieldsValue({
        llm: {
          ...form.getFieldValue('llm'),
          api_base: selectedProvider.baseUrl,
        },
      });
    }
  };

  // 渲染全局默认值提示
  const renderGlobalDefault = (path: string[], label: string) => {
    let value = globalConfig;
    for (const key of path) {
      value = value?.[key];
    }
    if (value !== undefined && value !== null && value !== '') {
      return (
        <Tooltip title={`全局默认值: ${typeof value === 'object' ? JSON.stringify(value) : value}`}>
          <Tag color="blue" style={{ marginLeft: 8 }}>
            <InfoCircleOutlined /> 有默认值
          </Tag>
        </Tooltip>
      );
    }
    return null;
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
        title={`我的设置 - ${user?.nickname || user?.username}`}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadConfigs}>
              刷新
            </Button>
            <Popconfirm
              title="确定要重置所有配置吗？"
              description="重置后将使用系统默认配置"
              onConfirm={() => handleReset()}
              okText="确定"
              cancelText="取消"
            >
              <Button icon={<DeleteOutlined />} danger>
                重置全部
              </Button>
            </Popconfirm>
            <Button
              icon={<ExperimentOutlined />}
              onClick={handleTestLLM}
              loading={testing}
            >
              测试 LLM
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              loading={saving}
            >
              保存配置
            </Button>
          </Space>
        }
      >
        <Alert
          message="个人配置说明"
          description="在这里配置的内容会覆盖系统默认配置。如果某项留空，则使用系统默认值。点击「重置」可以恢复使用默认配置。"
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Form form={form} layout="vertical">
          <Tabs
            defaultActiveKey="llm"
            items={[
              {
                key: 'llm',
                label: (
                  <span>
                    LLM 配置
                    {userConfig?.llm && Object.keys(userConfig.llm).length > 0 && (
                      <Tag color="green" style={{ marginLeft: 8 }}>已自定义</Tag>
                    )}
                  </span>
                ),
                children: (
                  <>
                    <Form.Item
                      label={
                        <span>
                          LLM 提供商
                          {renderGlobalDefault(['llm', 'provider'], 'LLM 提供商')}
                        </span>
                      }
                      name={['llm', 'provider']}
                    >
                      <Select
                        placeholder={`使用默认: ${globalConfig?.llm?.provider || '未设置'}`}
                        allowClear
                        onChange={handleProviderChange}
                      >
                        {llmProviders.map(provider => (
                          <Option key={provider.value} value={provider.value}>
                            {provider.label}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>

                    <Form.Item
                      label={
                        <span>
                          模型名称
                          {renderGlobalDefault(['llm', 'model'], '模型')}
                        </span>
                      }
                      name={['llm', 'model']}
                    >
                      <Input placeholder={`使用默认: ${globalConfig?.llm?.model || '未设置'}`} allowClear />
                    </Form.Item>

                    <Form.Item
                      label={
                        <span>
                          API 地址
                          {renderGlobalDefault(['llm', 'api_base'], 'API 地址')}
                        </span>
                      }
                      name={['llm', 'api_base']}
                    >
                      <Input placeholder={`使用默认: ${globalConfig?.llm?.api_base || '未设置'}`} allowClear />
                    </Form.Item>

                    <Form.Item
                      label={
                        <span>
                          API Key
                          {renderGlobalDefault(['llm', 'api_key'], 'API Key')}
                        </span>
                      }
                      name={['llm', 'api_key']}
                    >
                      <Input.Password placeholder="留空使用默认 API Key" allowClear />
                    </Form.Item>

                    <Form.Item
                      label="Temperature"
                      name={['llm', 'temperature']}
                    >
                      <InputNumber
                        min={0}
                        max={2}
                        step={0.1}
                        placeholder={`默认: ${globalConfig?.llm?.temperature || 0.7}`}
                        style={{ width: '100%' }}
                      />
                    </Form.Item>

                    <Form.Item
                      label="Max Tokens"
                      name={['llm', 'max_tokens']}
                    >
                      <InputNumber
                        min={1}
                        max={128000}
                        placeholder={`默认: ${globalConfig?.llm?.max_tokens || 2000}`}
                        style={{ width: '100%' }}
                      />
                    </Form.Item>

                    <Popconfirm
                      title="确定要重置 LLM 配置吗？"
                      onConfirm={() => handleReset('llm')}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button type="link" danger>
                        重置 LLM 配置
                      </Button>
                    </Popconfirm>
                  </>
                ),
              },
              {
                key: 'prompt',
                label: (
                  <span>
                    提示词
                    {(promptIsCustom || rulesIsCustom) && (
                      <Tag color="green" style={{ marginLeft: 8 }}>已自定义</Tag>
                    )}
                  </span>
                ),
                children: (
                  <Tabs
                    defaultActiveKey="persona"
                    size="small"
                    items={[
                      {
                        key: 'persona',
                        label: (
                          <span>
                            <FileTextOutlined /> 人设提示词
                            {promptIsCustom && <Tag color="green" style={{ marginLeft: 6 }}>已自定义</Tag>}
                          </span>
                        ),
                        children: (
                          <>
                            <Alert
                              message="人设提示词"
                              description="定义 AI 的角色、性格、世界观、语言风格和行为准则。这是 AI 的「灵魂」，用户可自由编辑。"
                              type="info"
                              showIcon
                              style={{ marginBottom: 16 }}
                            />
                            <Input.TextArea
                              rows={16}
                              value={promptContent}
                              onChange={e => setPromptContent(e.target.value)}
                              placeholder="输入人设提示词，定义 AI 的角色和行为方式..."
                              style={{ fontFamily: 'monospace', fontSize: 13 }}
                            />
                            <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                              <Button
                                type="primary"
                                icon={<SaveOutlined />}
                                loading={savingPrompt}
                                onClick={handleSavePrompt}
                              >
                                保存人设
                              </Button>
                              <Popconfirm
                                title="确定要重置人设提示词吗？"
                                description="将恢复为全局默认人设"
                                onConfirm={handleResetPrompt}
                                okText="确定"
                                cancelText="取消"
                              >
                                <Button icon={<DeleteOutlined />} danger>
                                  重置为默认
                                </Button>
                              </Popconfirm>
                              {promptIsCustom && (
                                <Tag color="green"><InfoCircleOutlined /> 当前使用自定义人设</Tag>
                              )}
                            </div>
                            {defaultPrompt && !promptIsCustom && (
                              <Alert
                                message="当前使用全局默认人设"
                                type="warning"
                                showIcon
                                style={{ marginTop: 12 }}
                              />
                            )}
                          </>
                        ),
                      },
                      {
                        key: 'rules',
                        label: (
                          <span>
                            <ToolOutlined /> 功能协议
                            {rulesIsCustom && <Tag color="green" style={{ marginLeft: 6 }}>已自定义</Tag>}
                          </span>
                        ),
                        children: (
                          <>
                            <Alert
                              message="功能协议"
                              description={
                                <span>
                                  定义 AI 可以使用的功能指令，如图片发送 <code>[GEN_IMG:]</code>、语音 <code>[TTS]</code>、任务委派 <code>[DELEGATE:]</code> 等。
                                  与人设分离，方便独立维护。留空则使用全局默认协议。
                                </span>
                              }
                              type="info"
                              showIcon
                              style={{ marginBottom: 16 }}
                            />
                            <Input.TextArea
                              rows={16}
                              value={rulesContent}
                              onChange={e => setRulesContent(e.target.value)}
                              placeholder="输入功能协议，定义 AI 可使用的功能指令..."
                              style={{ fontFamily: 'monospace', fontSize: 13 }}
                            />
                            <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                              <Button
                                type="primary"
                                icon={<SaveOutlined />}
                                loading={savingRules}
                                onClick={handleSaveRules}
                              >
                                保存协议
                              </Button>
                              <Popconfirm
                                title="确定要重置功能协议吗？"
                                description="将恢复为全局默认功能协议"
                                onConfirm={handleResetRules}
                                okText="确定"
                                cancelText="取消"
                              >
                                <Button icon={<DeleteOutlined />} danger>
                                  重置为默认
                                </Button>
                              </Popconfirm>
                              {rulesIsCustom && (
                                <Tag color="green"><InfoCircleOutlined /> 当前使用自定义协议</Tag>
                              )}
                            </div>
                            {defaultRules && !rulesIsCustom && (
                              <Alert
                                message="当前使用全局默认功能协议"
                                type="warning"
                                showIcon
                                style={{ marginTop: 12 }}
                              />
                            )}
                          </>
                        ),
                      },
                    ]}
                  />
                ),
              },
              {
                key: 'tts',
                label: (
                  <span>
                    TTS 配置
                    {userConfig?.tts && Object.keys(userConfig.tts).length > 0 && (
                      <Tag color="green" style={{ marginLeft: 8 }}>已自定义</Tag>
                    )}
                  </span>
                ),
                children: (
                  <>
                    <Form.Item
                      label="启用 TTS"
                      name={['tts', 'enabled']}
                      valuePropName="checked"
                    >
                      <Switch />
                    </Form.Item>

                    <Form.Item
                      label="TTS 提供商"
                      name={['tts', 'provider']}
                    >
                      <Select
                        placeholder={`使用默认: ${globalConfig?.tts?.provider || '未设置'}`}
                        allowClear
                      >
                        <Option value="edge">Edge TTS (免费)</Option>
                        <Option value="azure">Azure TTS</Option>
                        <Option value="openai">OpenAI TTS</Option>
                        <Option value="fish">Fish Audio</Option>
                        <Option value="qwen">通义千问 TTS</Option>
                      </Select>
                    </Form.Item>

                    <Alert
                      message="提示"
                      description="更多 TTS 配置（如音色、语速等）请前往 TTS 配置页面设置"
                      type="info"
                      showIcon
                      style={{ marginTop: 16 }}
                    />

                    <Popconfirm
                      title="确定要重置 TTS 配置吗？"
                      onConfirm={() => handleReset('tts')}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button type="link" danger style={{ marginTop: 16 }}>
                        重置 TTS 配置
                      </Button>
                    </Popconfirm>
                  </>
                ),
              },
              {
                key: 'account',
                label: (
                  <span>
                    <LinkOutlined /> 账号绑定
                    {(user?.qq_user_id || user?.linyu_user_id) && (
                      <Tag color="green" style={{ marginLeft: 8 }}>已绑定</Tag>
                    )}
                  </span>
                ),
                children: (
                  <>
                    <QQBindSection user={user} onSuccess={loadConfigs} />
                    <Divider />
                    <LinyuBindSection user={user} onSuccess={loadConfigs} />
                    <Divider />
                    <Alert
                      message="Linyu 独立双账号配置"
                      description="这里配置的是你专属 Linyu 会话使用的 AI 登录账号。你的聊天对象会自动使用当前绑定的 Linyu 身份，全局服务器地址也会自动继承，不需要再手填 HTTP / WS。"
                      type="warning"
                      showIcon
                      style={{ marginBottom: 16 }}
                    />
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['adapters', 'linyu', 'enabled']} label="启用个人 Linyu 会话" valuePropName="checked">
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item
                          name={['adapters', 'linyu', 'auto_bind_first_user']}
                          label="自动绑定首个聊天对象"
                          valuePropName="checked"
                          help="当你还没绑定自己的 Linyu 身份时，可临时锁定首个发消息的人作为聊天对象"
                        >
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name={['adapters', 'linyu', 'account']} label="AI 登录账号">
                          <Input placeholder="机器人账号" />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name={['adapters', 'linyu', 'password']} label="AI 登录密码">
                          <Input.Password placeholder="机器人账号密码" />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Alert
                      message="自动配对说明"
                      description={`系统会优先把 AI 账号配对到你当前绑定的 Linyu 账号：${user?.linyu_account || user?.linyu_user_id || '尚未绑定'}。若你还没绑定，可先完成上方「Linyu 账号绑定」，或临时开启“自动绑定首个聊天对象”。`}
                      type="info"
                      showIcon
                    />
                  </>
                ),
              },
              // 适配器配置 Tab（仅管理员可见）
              ...(isAdmin ? [{
                key: 'adapters',
                label: <span>🔌 适配器配置 <Tag color="orange">管理员</Tag></span>,
                children: (
                  <Form form={adapterForm} layout="vertical">
                    <Alert
                      message="适配器说明"
                      description="适配器决定机器人通过哪些渠道收发消息。修改后需重启后端服务才能生效。可同时启用多个适配器。"
                      type="info"
                      showIcon
                      style={{ marginBottom: 20 }}
                    />

                    {/* 控制台适配器 */}
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

                    {/* QQ 适配器 */}
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
                      <Form.Item noStyle shouldUpdate={(p: any, c: any) =>
                        p?.adapters?.qq?.enabled !== c?.adapters?.qq?.enabled
                      }>
                        {({ getFieldValue }: any) => getFieldValue(['adapters', 'qq', 'enabled']) ? (
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
                          </>
                        ) : (
                          <span style={{ color: '#aaa', fontSize: 13 }}>启用后展开详细配置</span>
                        )}
                      </Form.Item>
                    </Card>

                    {/* Linyu 适配器 */}
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
                      <Form.Item noStyle shouldUpdate={(p: any, c: any) =>
                        p?.adapters?.linyu?.enabled !== c?.adapters?.linyu?.enabled
                      }>
                        {({ getFieldValue }: any) => getFieldValue(['adapters', 'linyu', 'enabled']) ? (
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
                          </>
                        ) : (
                          <span style={{ color: '#aaa', fontSize: 13 }}>启用后展开详细配置</span>
                        )}
                      </Form.Item>
                    </Card>

                    <Button
                      type="primary"
                      icon={<SaveOutlined />}
                      onClick={handleSaveAdapters}
                      loading={savingAdapters}
                    >
                      保存适配器配置
                    </Button>
                  </Form>
                ),
              }] : []),
            ]}
          />
        </Form>
      </Card>
    </div>
  );
};

export default UserSettingsPage;
