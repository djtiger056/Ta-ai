import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Switch,
  Button,
  Space,
  message,
  Select,
  InputNumber,
  Typography,
  Divider,
  Alert,
  Row,
  Col,
  Image,
  Spin,
} from 'antd';
import { PictureOutlined, ExperimentOutlined } from '@ant-design/icons';
import { imageGenApi } from '@/services/api';
import { imageGenConfigProxy } from '@/services/configProxy';
import { Link } from 'react-router-dom';

const { Title, Text } = Typography;

interface ModelScopeConfig {
  api_key: string;
  model: string;
  timeout: number;
}

interface YunwuConfig {
  api_key: string;
  api_base: string;
  model: string;
  timeout: number;
}

interface KlingApiConfig {
  api_base: string;
  api_key: string;
  model: string;
  timeout: number;
  size: string;
  poll_interval: number;
  transport: string;
  target_url: string;
  response_format: string;
}

interface ImageGenConfig {
  enabled: boolean;
  provider: string;
  fallback_provider: string;
  enable_fallback: boolean;
  modelscope: ModelScopeConfig;
  yunwu: YunwuConfig;
  kling_api: KlingApiConfig;
  trigger_keywords: string[];
  generating_message: string;
  error_message: string;
  success_message: string;
}

const providerOptions = [
  { value: 'modelscope', label: '魔搭社区' },
  { value: 'yunwu', label: 'yunwu.ai' },
  { value: 'kling_api', label: '本地 kling-api' },
];

const ImageGenPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [generateLoading, setGenerateLoading] = useState(false);
  const [testImage, setTestImage] = useState<string | null>(null);
  const [config, setConfig] = useState<ImageGenConfig>({
    enabled: true,
    provider: 'modelscope',
    fallback_provider: 'yunwu',
    enable_fallback: true,
    modelscope: {
      api_key: '',
      model: 'Tongyi-MAI/Z-Image-Turbo',
      timeout: 120,
    },
    yunwu: {
      api_key: '',
      api_base: 'https://yunwu.ai/v1',
      model: 'jimeng-4.5',
      timeout: 120,
    },
    kling_api: {
      api_base: 'http://127.0.0.1:18080',
      api_key: '',
      model: 'kling-v2-1',
      timeout: 180,
      size: '1024x1024',
      poll_interval: 3,
      transport: 'web',
      target_url: 'https://klingai.com/app/image/new',
      response_format: 'url',
    },
    trigger_keywords: ['画', '生成图片', '生图', '绘制'],
    generating_message: '🎨 正在为你生成图片，请稍候...',
    error_message: '😢 图片生成失败：{error}',
    success_message: '✨ 图片已生成完成！',
  });

  const modelscopeModels = [
    'Tongyi-MAI/Z-Image-Turbo',
    'AI-ModelScope/stable-diffusion-v1-5',
    'AI-ModelScope/stable-diffusion-xl-base-1.0',
  ];

  const yunwuModels = ['jimeng-4.5', 'stable-diffusion-xl', 'dall-e-3'];
  const klingModels = ['kling-v2-1'];
  const currentProvider = Form.useWatch('provider', form) || 'modelscope';

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await imageGenConfigProxy.getConfig();
      setConfig(data);
      form.setFieldsValue(data);
    } catch (error) {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async (values: ImageGenConfig) => {
    try {
      setLoading(true);
      await imageGenConfigProxy.updateConfig(values);
      message.success('配置保存成功');
      setConfig(values);
    } catch (error) {
      message.error('配置保存失败');
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async () => {
    try {
      setTestLoading(true);
      const success = await imageGenApi.testImageGenConnection();
      if (success) {
        message.success('连接测试成功');
      } else {
        message.error('连接测试失败');
      }
    } catch (error) {
      message.error('连接测试失败');
    } finally {
      setTestLoading(false);
    }
  };

  const generateTestImage = async () => {
    try {
      setGenerateLoading(true);
      setTestImage(null);
      const result = await imageGenApi.generateImage('一只可爱的小猫咪在花园里玩耍');
      if (result.success && result.image_data) {
        setTestImage(`data:image/jpeg;base64,${result.image_data}`);
        message.success('测试图片生成成功');
      } else {
        message.error(`图片生成失败：${result.message}`);
      }
    } catch (error) {
      message.error('图片生成失败');
    } finally {
      setGenerateLoading(false);
    }
  };

  const renderProviderFields = () => {
    if (currentProvider === 'modelscope') {
      return (
        <>
          <Divider>魔搭社区配置</Divider>
          <Form.Item
            name={['modelscope', 'api_key']}
            label="API密钥"
            rules={[{ required: true, message: '请输入API密钥' }]}
          >
            <Input.Password placeholder="请输入魔搭社区API密钥" />
          </Form.Item>
          <Form.Item
            name={['modelscope', 'model']}
            label="模型"
            rules={[{ required: true, message: '请选择模型' }]}
          >
            <Select options={modelscopeModels.map((model) => ({ value: model, label: model }))} />
          </Form.Item>
          <Form.Item name={['modelscope', 'timeout']} label="超时时间（秒）">
            <InputNumber min={30} max={300} style={{ width: '100%' }} />
          </Form.Item>
        </>
      );
    }

    if (currentProvider === 'yunwu') {
      return (
        <>
          <Divider>yunwu.ai 配置</Divider>
          <Form.Item
            name={['yunwu', 'api_key']}
            label="API密钥"
            rules={[{ required: true, message: '请输入API密钥' }]}
          >
            <Input.Password placeholder="请输入 yunwu.ai API密钥" />
          </Form.Item>
          <Form.Item name={['yunwu', 'api_base']} label="API地址">
            <Input placeholder="https://yunwu.ai/v1" />
          </Form.Item>
          <Form.Item
            name={['yunwu', 'model']}
            label="模型"
            rules={[{ required: true, message: '请选择模型' }]}
          >
            <Select options={yunwuModels.map((model) => ({ value: model, label: model }))} />
          </Form.Item>
          <Form.Item name={['yunwu', 'timeout']} label="超时时间（秒）">
            <InputNumber min={30} max={300} style={{ width: '100%' }} />
          </Form.Item>
        </>
      );
    }

    return (
      <>
        <Divider>本地 kling-api 配置</Divider>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="接入说明"
          description="这里填写 /myproject/kling-api 暴露出来的本地接口地址。若服务启用了 SERVER_API_KEYS，需要把对应 key 也填上。"
        />
        <Form.Item
          name={['kling_api', 'api_base']}
          label="API地址"
          rules={[{ required: true, message: '请输入 kling-api 地址' }]}
        >
          <Input placeholder="http://127.0.0.1:18080" />
        </Form.Item>
        <Form.Item name={['kling_api', 'api_key']} label="API Key">
          <Input.Password placeholder="未开启鉴权可留空" />
        </Form.Item>
        <Form.Item
          name={['kling_api', 'model']}
          label="模型"
          rules={[{ required: true, message: '请选择模型' }]}
        >
          <Select options={klingModels.map((model) => ({ value: model, label: model }))} />
        </Form.Item>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name={['kling_api', 'size']} label="尺寸">
              <Select
                options={[
                  { value: '1024x1024', label: '1024x1024' },
                  { value: '768x1344', label: '768x1344' },
                  { value: '1344x768', label: '1344x768' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name={['kling_api', 'timeout']} label="超时时间（秒）">
              <InputNumber min={30} max={600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name={['kling_api', 'poll_interval']} label="轮询间隔（秒）">
              <InputNumber min={0.5} max={30} step={0.5} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name={['kling_api', 'transport']} label="传输模式">
              <Select options={[{ value: 'web', label: 'web' }]} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name={['kling_api', 'target_url']} label="目标页面地址">
          <Input placeholder="https://klingai.com/app/image/new" />
        </Form.Item>
        <Form.Item name={['kling_api', 'response_format']} label="响应格式">
          <Select options={[{ value: 'url', label: 'url' }, { value: 'b64_json', label: 'b64_json' }]} />
        </Form.Item>
      </>
    );
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>
        <PictureOutlined /> 图像生成配置
      </Title>

      <Alert
        message="多用户提示"
        description={
          <div>
            此页面为<strong>全局</strong>图像生成配置；如需为不同用户设置不同的生图提供商/模型/密钥，请到 <Link to="/user-config">个人配置</Link> 页面配置。
          </div>
        }
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Row gutter={[24, 24]}>
        <Col span={16}>
          <Card title="基础配置" loading={loading}>
            <Form form={form} layout="vertical" initialValues={config} onFinish={saveConfig}>
              <Form.Item name="enabled" label="启用图像生成" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="provider" label="主提供商">
                    <Select options={providerOptions} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="enable_fallback" label="启用自动降级" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item noStyle shouldUpdate>
                {({ getFieldValue }) => (
                  <Form.Item name="fallback_provider" label="备用提供商">
                    <Select
                      options={providerOptions.filter((item) => item.value !== getFieldValue('provider'))}
                      allowClear
                      placeholder="主提供商失败时使用"
                    />
                  </Form.Item>
                )}
              </Form.Item>

              {renderProviderFields()}

              <Divider>触发配置</Divider>
              <Form.Item
                name="trigger_keywords"
                label="触发关键词"
                rules={[{ required: true, message: '请输入触发关键词' }]}
              >
                <Select mode="tags" placeholder="输入触发关键词，按回车添加" style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="generating_message" label="生成中消息">
                <Input placeholder="图片生成时显示的消息" />
              </Form.Item>
              <Form.Item name="error_message" label="错误消息">
                <Input placeholder="生成失败时显示的消息" />
              </Form.Item>
              <Form.Item name="success_message" label="成功消息">
                <Input placeholder="生成成功时显示的消息" />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" loading={loading}>
                    保存配置
                  </Button>
                  <Button icon={<ExperimentOutlined />} onClick={testConnection} loading={testLoading}>
                    测试连接
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col span={8}>
          <Card title="测试功能">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button type="primary" onClick={generateTestImage} loading={generateLoading} block>
                生成测试图片
              </Button>

              {generateLoading && (
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <Spin size="large" />
                  <div style={{ marginTop: '10px' }}>正在生成图片，请稍候...</div>
                </div>
              )}

              {testImage && (
                <div>
                  <Text strong>测试结果：</Text>
                  <Image src={testImage} alt="测试图片" style={{ width: '100%', marginTop: '10px' }} />
                </div>
              )}
            </Space>
          </Card>

          <Card title="使用说明" style={{ marginTop: '16px' }}>
            <Alert
              message="使用方法"
              description={
                <div>
                  <p>在 QQ / 聊天端里发送包含以下关键词的消息即可触发生图：</p>
                  <ul>
                    <li>画一只可爱的小猫</li>
                    <li>生成图片：美丽的风景</li>
                    <li>帮我生图，主题是星空</li>
                    <li>绘制一座宏伟的城堡</li>
                  </ul>
                  <p>如果主提供商设为本地 kling-api，系统会转调你已经跑通的 kling 服务。</p>
                </div>
              }
              type="info"
              showIcon
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ImageGenPage;
