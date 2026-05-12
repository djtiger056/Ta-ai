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
} from 'antd';
import { 
  SaveOutlined, 
  ExperimentOutlined, 
  ReloadOutlined,
  InfoCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { userConfigApi, configApi } from '@/services/api';
import { useAuth } from '../contexts/AuthContext';

const { Option } = Select;
const { TextArea } = Input;

/**
 * 用户个人设置页面
 * 用户可以在这里配置自己的个性化设置，覆盖全局默认配置
 */
const UserSettingsPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [userConfig, setUserConfig] = useState<any>(null);
  const [globalConfig, setGlobalConfig] = useState<any>(null);
  const { user } = useAuth();

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      // 并行加载用户配置和全局配置
      const [userCfg, globalCfg] = await Promise.all([
        userConfigApi.getConfig(),
        configApi.getConfig(),
      ]);
      
      setUserConfig(userCfg);
      setGlobalConfig(globalCfg);
      
      // 设置表单值（用户配置优先，否则显示全局配置作为占位符）
      form.setFieldsValue({
        system_prompt: userCfg.system_prompt || '',
        llm: userCfg.llm || {},
        tts: userCfg.tts || {},
      });
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
      
      // 构建更新数据，只包含用户实际填写的字段
      const updateData: any = {};
      
      if (values.system_prompt) {
        updateData.system_prompt = values.system_prompt;
      }
      
      if (values.llm && Object.keys(values.llm).some(k => values.llm[k])) {
        updateData.llm = values.llm;
      }
      
      if (values.tts && Object.keys(values.tts).some(k => values.tts[k])) {
        updateData.tts = values.tts;
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

  const handleReset = async (configType?: string) => {
    try {
      await userConfigApi.resetConfig(configType);
      message.success(configType ? `${configType} 配置已重置` : '所有配置已重置');
      loadConfigs();
    } catch (error: any) {
      message.error('重置失败: ' + (error.response?.data?.detail || error.message));
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
                    系统提示词
                    {userConfig?.system_prompt && (
                      <Tag color="green" style={{ marginLeft: 8 }}>已自定义</Tag>
                    )}
                  </span>
                ),
                children: (
                  <>
                    <Form.Item
                      label="我的系统提示词"
                      name="system_prompt"
                      help="定义 AI 的角色和行为方式。留空则使用系统默认提示词。"
                    >
                      <TextArea
                        rows={12}
                        placeholder={globalConfig?.system_prompt ? `默认提示词:\n${globalConfig.system_prompt.substring(0, 200)}...` : '输入你的自定义系统提示词'}
                        allowClear
                      />
                    </Form.Item>

                    {globalConfig?.system_prompt && (
                      <Alert
                        message="当前默认系统提示词"
                        description={
                          <pre style={{ whiteSpace: 'pre-wrap', maxHeight: '200px', overflow: 'auto' }}>
                            {globalConfig.system_prompt}
                          </pre>
                        }
                        type="info"
                        style={{ marginTop: 16 }}
                      />
                    )}

                    <Popconfirm
                      title="确定要重置系统提示词吗？"
                      onConfirm={() => handleReset('system_prompt')}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button type="link" danger style={{ marginTop: 16 }}>
                        重置系统提示词
                      </Button>
                    </Popconfirm>
                  </>
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
            ]}
          />
        </Form>
      </Card>
    </div>
  );
};

export default UserSettingsPage;
