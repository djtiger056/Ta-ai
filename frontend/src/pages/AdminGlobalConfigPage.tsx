import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Tabs, Switch, InputNumber, Select, Spin, Alert, Divider } from 'antd';
import { SaveOutlined, ReloadOutlined, GlobalOutlined } from '@ant-design/icons';
import axios from 'axios';

const { TextArea } = Input;
const { Option } = Select;

/**
 * 管理员全局配置页面
 * 用于配置系统默认配置，作为用户未自定义时的兜底配置
 */
const AdminGlobalConfigPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<any>(null);
  const [form] = Form.useForm();

  // 加载全局配置
  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/config');
      setConfig(response.data);
      form.setFieldsValue(flattenConfig(response.data));
    } catch (error: any) {
      message.error('加载配置失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  // 将嵌套配置扁平化用于表单
  const flattenConfig = (cfg: any) => {
    return {
      // LLM 配置
      llm_provider: cfg?.llm?.provider,
      llm_api_key: cfg?.llm?.api_key,
      llm_api_base: cfg?.llm?.api_base,
      llm_model: cfg?.llm?.model,
      llm_temperature: cfg?.llm?.temperature,
      llm_max_tokens: cfg?.llm?.max_tokens,
      // 系统提示词
      system_prompt: cfg?.system_prompt,
      // TTS 配置
      tts_enabled: cfg?.tts?.enabled,
      tts_provider: cfg?.tts?.provider,
      // ASR 配置
      asr_enabled: cfg?.asr?.enabled,
      asr_provider: cfg?.asr?.provider,
      // 图像生成配置
      image_gen_enabled: cfg?.image_generation?.enabled,
      image_gen_provider: cfg?.image_generation?.provider,
      // 视觉识别配置
      vision_enabled: cfg?.vision?.enabled,
      vision_provider: cfg?.vision?.provider,
      // 记忆配置
      memory_enabled: cfg?.memory?.enabled,
      memory_provider: cfg?.memory?.provider,
    };
  };

  // 保存配置
  const handleSave = async (values: any) => {
    setSaving(true);
    try {
      // 构建更新的配置对象
      const updateConfig: any = {};
      
      // LLM 配置
      if (values.llm_provider || values.llm_api_key || values.llm_api_base || values.llm_model) {
        updateConfig.llm = {
          ...config?.llm,
          provider: values.llm_provider,
          api_key: values.llm_api_key,
          api_base: values.llm_api_base,
          model: values.llm_model,
          temperature: values.llm_temperature,
          max_tokens: values.llm_max_tokens,
        };
      }
      
      // 系统提示词
      if (values.system_prompt !== undefined) {
        updateConfig.system_prompt = values.system_prompt;
      }

      await axios.post('/api/config', updateConfig);
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
          <Button icon={<ReloadOutlined />} onClick={loadConfig}>
            刷新
          </Button>
        }
      >
        <Alert
          message="全局配置说明"
          description="此处配置的是系统默认配置，当用户没有自定义某项配置时，将使用这里的默认值。用户自定义的配置会覆盖全局配置。"
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          <Tabs
            defaultActiveKey="llm"
            items={[
              {
                key: 'llm',
                label: 'LLM 配置',
                children: (
                  <>
                    <Form.Item name="llm_provider" label="LLM 提供商">
                      <Select placeholder="选择 LLM 提供商">
                        <Option value="openai">OpenAI</Option>
                        <Option value="deepseek">DeepSeek</Option>
                        <Option value="qwen">通义千问</Option>
                        <Option value="zhipu">智谱 AI</Option>
                        <Option value="ollama">Ollama (本地)</Option>
                      </Select>
                    </Form.Item>
                    <Form.Item name="llm_api_base" label="API 地址">
                      <Input placeholder="https://api.openai.com/v1" />
                    </Form.Item>
                    <Form.Item name="llm_api_key" label="API Key">
                      <Input.Password placeholder="sk-..." />
                    </Form.Item>
                    <Form.Item name="llm_model" label="模型名称">
                      <Input placeholder="gpt-4o-mini" />
                    </Form.Item>
                    <Form.Item name="llm_temperature" label="Temperature">
                      <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
                    </Form.Item>
                    <Form.Item name="llm_max_tokens" label="Max Tokens">
                      <InputNumber min={1} max={128000} style={{ width: '100%' }} />
                    </Form.Item>
                  </>
                ),
              },
              {
                key: 'prompt',
                label: '系统提示词',
                children: (
                  <Form.Item name="system_prompt" label="默认系统提示词">
                    <TextArea 
                      rows={15} 
                      placeholder="输入默认的系统提示词，用户未自定义时将使用此提示词"
                    />
                  </Form.Item>
                ),
              },
              {
                key: 'tts',
                label: 'TTS 配置',
                children: (
                  <>
                    <Form.Item name="tts_enabled" label="启用 TTS" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name="tts_provider" label="TTS 提供商">
                      <Select placeholder="选择 TTS 提供商">
                        <Option value="edge">Edge TTS (免费)</Option>
                        <Option value="azure">Azure TTS</Option>
                        <Option value="openai">OpenAI TTS</Option>
                        <Option value="fish">Fish Audio</Option>
                        <Option value="qwen">通义千问 TTS</Option>
                      </Select>
                    </Form.Item>
                    <Alert
                      message="提示"
                      description="TTS 的详细配置（如音色、语速等）请在对应的配置页面设置"
                      type="info"
                      showIcon
                      style={{ marginTop: 16 }}
                    />
                  </>
                ),
              },
              {
                key: 'asr',
                label: 'ASR 配置',
                children: (
                  <>
                    <Form.Item name="asr_enabled" label="启用语音识别" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name="asr_provider" label="ASR 提供商">
                      <Select placeholder="选择 ASR 提供商">
                        <Option value="siliconflow">SiliconFlow</Option>
                        <Option value="qwen">通义千问 ASR</Option>
                        <Option value="assemblyai">AssemblyAI</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },
              {
                key: 'image',
                label: '图像生成',
                children: (
                  <>
                    <Form.Item name="image_gen_enabled" label="启用图像生成" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name="image_gen_provider" label="图像生成提供商">
                      <Select placeholder="选择图像生成提供商">
                        <Option value="siliconflow">SiliconFlow</Option>
                        <Option value="openai">OpenAI DALL-E</Option>
                        <Option value="stability">Stability AI</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },
              {
                key: 'vision',
                label: '视觉识别',
                children: (
                  <>
                    <Form.Item name="vision_enabled" label="启用视觉识别" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name="vision_provider" label="视觉识别提供商">
                      <Select placeholder="选择视觉识别提供商">
                        <Option value="openai">OpenAI Vision</Option>
                        <Option value="qwen">通义千问 VL</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },
              {
                key: 'memory',
                label: '记忆系统',
                children: (
                  <>
                    <Form.Item name="memory_enabled" label="启用记忆系统" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Form.Item name="memory_provider" label="记忆存储方式">
                      <Select placeholder="选择记忆存储方式">
                        <Option value="local">本地向量存储</Option>
                        <Option value="memobase">Memobase (外部服务)</Option>
                      </Select>
                    </Form.Item>
                  </>
                ),
              },
            ]}
          />

          <Divider />

          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit" 
              icon={<SaveOutlined />}
              loading={saving}
              size="large"
            >
              保存全局配置
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default AdminGlobalConfigPage;
