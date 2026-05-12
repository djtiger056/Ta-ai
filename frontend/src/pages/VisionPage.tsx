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
  Spin,
  Tabs,
  Tag
} from 'antd';
import { EyeOutlined, ExperimentOutlined, CameraOutlined } from '@ant-design/icons';
import { visionApi } from '@/services/api';
import { visionConfigProxy } from '@/services/configProxy';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface VisionConfig {
  enabled: boolean;
  provider: string;
  modelscope: {
    api_key: string;
    model: string;
    base_url: string;
    timeout: number;
  };
  instruction_text: string;
  auto_send_to_llm: boolean;
  follow_up_timeout: number;
  trigger_keywords: string[];
  error_message: string;
}

const VisionPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [config, setConfig] = useState<VisionConfig>({
    enabled: false,
    provider: 'modelscope',
    modelscope: {
      api_key: '',
      model: 'Qwen/Qwen3-VL-30B-A3B-Instruct',
      base_url: 'https://api-inference.modelscope.cn/v1',
      timeout: 120
    },
    instruction_text: '这是一张图片的描述，请根据描述生成一段合适的话语：',
    auto_send_to_llm: true,
    follow_up_timeout: 5.0,
    trigger_keywords: ['识别图片', '描述图片', '这是什么图'],
    error_message: '😢 图片识别失败：{error}'
  });

  // 可用的视觉模型列表
  const availableModels = [
    'Qwen/Qwen3-VL-30B-A3B-Instruct',
    'Qwen/Qwen2-VL-72B-Instruct',
    'qwen/Qwen-VL-Chat'
  ];

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      console.log('正在加载视觉识别配置...');
      const data = await visionConfigProxy.getConfig();
      console.log('配置加载成功:', data);
      setConfig(data);
      form.setFieldsValue(data);
    } catch (error: any) {
      console.error('加载配置失败:', error);
      if (error.response) {
        console.error('错误响应:', error.response.data);
        message.error('加载配置失败，请检查后端服务');
      } else {
        message.error('加载配置失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async (values: VisionConfig) => {
    try {
      setLoading(true);
      console.log('保存配置:', values);
      await visionConfigProxy.updateConfig(values);
      message.success('配置保存成功');
      // 保存成功后重新加载配置，确保与后端同步
      await loadConfig();
    } catch (error: any) {
      console.error('保存配置失败:', error);
      if (error.response) {
        console.error('错误响应:', error.response.data);
        message.error(`配置保存失败: ${error.response.data.detail || error.message}`);
      } else {
        message.error('配置保存失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async () => {
    try {
      setTestLoading(true);
      const success = await visionApi.testVisionConnection();
      
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

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>
        <EyeOutlined /> 视觉识别配置
      </Title>
      
      <Row gutter={[24, 24]}>
        <Col span={16}>
          <Card title="基础配置" loading={loading}>
            <Form
              form={form}
              layout="vertical"
              initialValues={config}
              onFinish={saveConfig}
            >
              <Tabs defaultActiveKey="basic">
                <Tabs.TabPane tab="基础设置" key="basic">
                  <Form.Item
                    name="enabled"
                    label="启用视觉识别"
                    valuePropName="checked"
                  >
                    <Switch />
                  </Form.Item>

                  <Form.Item
                    name="provider"
                    label="提供商"
                  >
                    <Select>
                      <Select.Option value="modelscope">魔搭社区</Select.Option>
                    </Select>
                  </Form.Item>

                  <Form.Item
                    name="auto_send_to_llm"
                    label="自动发送识别结果给LLM"
                    valuePropName="checked"
                    help="识别图片后自动将结果发送给LLM生成回复"
                  >
                    <Switch />
                  </Form.Item>

                  <Form.Item
                    name="follow_up_timeout"
                    label="等待补充消息超时时间（秒）"
                    help="图片识别完成后，等待用户发送补充消息的超时时间。例如：用户发送图片后，在5秒内又发送了文字消息，这些消息会被合并处理"
                  >
                    <InputNumber min={0} max={30} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>

                  <Form.Item
                    name="instruction_text"
                    label="LLM指令文本"
                    help="识别图片后，将此文本与识别结果一起发送给LLM，指导LLM生成合适的话语"
                  >
                    <TextArea
                      rows={4}
                      placeholder="这是一张图片的描述，请根据描述生成一段合适的话语："
                    />
                  </Form.Item>
                </Tabs.TabPane>

                <Tabs.TabPane tab="API配置" key="api">
                  <Divider>魔搭社区配置</Divider>
                  
                  <Form.Item
                    name={['modelscope', 'base_url']}
                    label="API基础地址"
                    rules={[{ required: true, message: '请输入API基础地址' }]}
                  >
                    <Input placeholder="https://api-inference.modelscope.cn/v1" />
                  </Form.Item>

                  <Form.Item
                    name={['modelscope', 'api_key']}
                    label="API密钥"
                    rules={[{ required: true, message: '请输入API密钥' }]}
                  >
                    <Input.Password placeholder="请输入魔搭社区API密钥" />
                  </Form.Item>

                  <Form.Item
                    name={['modelscope', 'model']}
                    label="视觉模型"
                    rules={[{ required: true, message: '请选择视觉模型' }]}
                  >
                    <Select>
                      {availableModels.map(model => (
                        <Select.Option key={model} value={model}>
                          {model}
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Form.Item
                    name={['modelscope', 'timeout']}
                    label="超时时间（秒）"
                  >
                    <InputNumber min={30} max={300} />
                  </Form.Item>
                </Tabs.TabPane>

                <Tabs.TabPane tab="消息配置" key="messages">
                  <Divider>触发配置</Divider>

                  <Form.Item
                    name="trigger_keywords"
                    label="触发关键词"
                    help="在文本消息中触发图片识别的关键词（图片识别主要基于图片本身，此功能为可选）"
                  >
                    <Select
                      mode="tags"
                      placeholder="输入触发关键词，按回车添加"
                      style={{ width: '100%' }}
                    />
                  </Form.Item>

                  <Divider>消息模板</Divider>



                  <Form.Item
                    name="error_message"
                    label="错误消息"
                  >
                    <Input placeholder="识别失败时显示的消息，可使用{error}占位符" />
                  </Form.Item>


                </Tabs.TabPane>
              </Tabs>

              <Divider />
              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" loading={loading}>
                    保存配置
                  </Button>
                  <Button 
                    icon={<ExperimentOutlined />} 
                    onClick={testConnection}
                    loading={testLoading}
                  >
                    测试连接
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col span={8}>
          <Card title="功能介绍">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Alert
                message="视觉识别功能"
                description={
                  <div>
                    <p><strong>功能说明：</strong></p>
                    <p>当QQ用户发送图片时，自动识别图片内容，并将识别结果发送给LLM生成回复。</p>
                    
                    <p><strong>使用流程：</strong></p>
                    <ol>
                      <li>用户在QQ中发送图片</li>
                      <li>系统自动识别图片内容</li>
                      <li>将识别结果与指令文本结合</li>
                      <li>发送给LLM生成自然语言回复</li>
                      <li>将回复发送给用户</li>
                    </ol>
                    
                    <p><strong>注意事项：</strong></p>
                    <ul>
                      <li>需要配置有效的魔搭社区API密钥</li>
                      <li>建议使用Qwen-VL系列模型</li>
                      <li>识别过程可能需要几秒钟时间</li>
                    </ul>
                  </div>
                }
                type="info"
                showIcon
              />
              
              <Alert
                message="配置说明"
                description={
                  <div>
                    <p><strong>LLM指令文本：</strong></p>
                    <p>此文本会与图片识别结果一起发送给LLM，用于指导LLM生成合适的话语。</p>
                    <p>例如："这是一张图片的描述，请根据描述生成一段合适的话语："</p>
                    
                    <p><strong>自动发送给LLM：</strong></p>
                    <p>开启后，识别结果会自动发送给LLM；关闭后，只进行图片识别而不生成回复。</p>
                    
                    <p><strong>触发关键词：</strong></p>
                    <p>主要用于文本触发识别（如"识别这张图片"），图片识别主要基于图片本身。</p>
                  </div>
                }
                type="warning"
                showIcon
              />
            </Space>
          </Card>

          <Card title="状态信息" style={{ marginTop: '16px' }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>当前状态：</Text>
                <Tag color={config.enabled ? 'green' : 'red'} style={{ marginLeft: '8px' }}>
                  {config.enabled ? '已启用' : '已禁用'}
                </Tag>
              </div>
              
              <div>
                <Text strong>当前模型：</Text>
                <Text style={{ marginLeft: '8px' }}>{config.modelscope.model}</Text>
              </div>
              
              <div>
                <Text strong>API配置：</Text>
                <Text style={{ marginLeft: '8px' }}>
                  {config.modelscope.api_key ? '已配置' : '未配置'}
                </Text>
              </div>
              
              <Divider />
              
              <Alert
                message="测试说明"
                description="点击测试连接按钮可以验证API密钥和模型连接是否正常。"
                type="info"
                showIcon
              />
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default VisionPage;