import React, { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, message, Radio, Space, Spin, Typography } from 'antd'
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons'

import { promptApi, userConfigApi, UserConfig } from '@/services/api'

const { TextArea } = Input
const { Text } = Typography

type ChatMode = 'companion' | 'roleplay'

const RoleplayModePage: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [promptIsCustom, setPromptIsCustom] = useState(false)
  const [userConfig, setUserConfig] = useState<UserConfig | null>(null)
  const [defaultExitSummaryPrompt, setDefaultExitSummaryPrompt] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const [cfg, promptData, exitSummaryPrompt] = await Promise.all([
        userConfigApi.getConfig(),
        promptApi.getRoleplayPrompt(),
        promptApi.getDefaultRoleplayExitSummaryPrompt(),
      ])
      setUserConfig(cfg)
      setPromptIsCustom(promptData.is_custom)
      setDefaultExitSummaryPrompt(exitSummaryPrompt)
      form.setFieldsValue({
        chat_mode: cfg.preferences?.chat_mode || 'companion',
        roleplay_prompt: promptData.content,
        roleplay_exit_summary_prompt:
          cfg.preferences?.roleplay_exit_summary_prompt || exitSummaryPrompt,
      })
    } catch (error) {
      message.error('加载情景模式配置失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      const nextMode: ChatMode = values.chat_mode || 'companion'
      const nextPreferences = {
        ...(userConfig?.preferences || {}),
        chat_mode: nextMode,
        roleplay_exit_summary_prompt: values.roleplay_exit_summary_prompt,
      }
      await Promise.all([
        userConfigApi.updateConfig({ preferences: nextPreferences }),
        promptApi.updateRoleplayPrompt(values.roleplay_prompt),
      ])
      message.success('情景模式配置已保存')
      await loadData()
    } catch (error) {
      message.error('保存情景模式配置失败')
      console.error(error)
    } finally {
      setSaving(false)
    }
  }

  const handleResetPrompt = async () => {
    setSaving(true)
    try {
      await promptApi.resetRoleplayPrompt()
      const defaultPrompt = await promptApi.getDefaultRoleplayPrompt()
      form.setFieldValue('roleplay_prompt', defaultPrompt)
      setPromptIsCustom(false)
      message.success('已恢复默认情景演绎提示词')
    } catch (error) {
      message.error('恢复默认提示词失败')
      console.error(error)
    } finally {
      setSaving(false)
    }
  }

  const handleResetExitSummaryPrompt = () => {
    form.setFieldValue('roleplay_exit_summary_prompt', defaultExitSummaryPrompt)
    message.success('已恢复默认结束摘要提示词')
  }

  if (loading) {
    return (
      <Card>
        <Spin /> <span style={{ marginLeft: 8 }}>加载中...</span>
      </Card>
    )
  }

  return (
    <Card
      title="情景模式"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={handleResetPrompt} disabled={saving}>
            恢复默认提示词
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleResetExitSummaryPrompt} disabled={saving}>
            恢复默认结束摘要提示词
          </Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="情景演绎模式会影响 QQ / Linyu 聊天账号"
        description="开启后仅保留纯文本情景对话，并使用独立短期/中期记忆；TTS、ASR、图片、视觉识别、表情包和 Agent 委派都会跳过。"
      />

      <Form form={form} layout="vertical">
        <Form.Item label="聊天模式" name="chat_mode" rules={[{ required: true }]}>
          <Radio.Group>
            <Radio.Button value="companion">AI伴侣模式</Radio.Button>
            <Radio.Button value="roleplay">情景演绎模式</Radio.Button>
          </Radio.Group>
        </Form.Item>

        <Form.Item
          label={
            <Space>
              <span>情景演绎提示词</span>
              <Text type={promptIsCustom ? 'success' : 'secondary'}>
                {promptIsCustom ? '已自定义' : '默认'}
              </Text>
            </Space>
          }
          name="roleplay_prompt"
          rules={[{ required: true, message: '请输入情景演绎提示词' }]}
        >
          <TextArea rows={18} style={{ fontFamily: 'monospace' }} />
        </Form.Item>

        <Form.Item
          label="情景结束摘要提示词"
          name="roleplay_exit_summary_prompt"
          rules={[{ required: true, message: '请输入情景结束摘要提示词' }]}
        >
          <TextArea rows={10} style={{ fontFamily: 'monospace' }} />
        </Form.Item>
      </Form>
    </Card>
  )
}

export default RoleplayModePage
