import React, { useState, useEffect, useRef } from 'react'
import { 
  Card, 
  Form, 
  Input, 
  InputNumber, 
  Switch, 
  Select,
  Button, 
  message, 
  Tabs, 
  Space,
  Divider,
  Row,
  Col,
  Table,
  Tag,
  Popconfirm,
  Descriptions,
  Statistic,
  Tooltip,
  Alert
} from 'antd'
import { 
  SaveOutlined, 
  ExperimentOutlined, 
  DatabaseOutlined,
  DeleteOutlined,
  SearchOutlined,
  EyeOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import { memoryApi, userConfigApi, UserConfig } from '@/services/api'

const { TabPane } = Tabs
const { TextArea } = Input

interface MemoryConfig {
  short_term_enabled: boolean
  mid_term_enabled: boolean
  mid_term_context_count?: number
  long_term_enabled: boolean
  long_term_strategy?: string
  external_memory_provider?: string
  external_memory_base_url?: string | null
  external_memory_api_key?: string
  external_memory_timeout?: number
  external_memory_prefer_topics?: string[]
  embedding_provider?: string
  embedding_model: string
  embedding_api_base?: string | null
  embedding_api_key?: string
  embedding_timeout?: number
  embedding_dimensions?: number | null
  rag_top_k: number
  rag_score_threshold: number
  short_term_max_rounds: number
  short_term_keep_rounds?: number
  pending_enabled?: boolean
  pending_chunk_rounds?: number
  pending_delete_after_summary?: boolean
  pending_overlap_messages?: number
  summarizer_enabled?: boolean
  summarizer_llm?: {
    provider?: string
    api_base?: string
    api_key?: string
    model?: string
    temperature?: number
    max_tokens?: number
  }
  summarizer_max_facts?: number
  summarizer_fact_min_importance?: number | null
  legacy_auto_extract_enabled?: boolean
  summary_interval: number
  summary_max_length: number
  max_summaries: number
  max_long_term_memories: number
}

interface MemoryItem {
  id: string
  content: string
  memory_type?: string
  importance?: number
  similarity?: number
  metadata?: any
  created_at?: string
  updated_at?: string
}

interface MemorySummary {
  id: number
  user_id: string
  session_id: string
  summary: string
  conversation_range: string
  metadata?: any
  created_at?: string
}

interface MemoryUserInfo {
  user_id: string
  display_name: string
  selector_key?: string
  channel?: string
}

const EMBEDDING_HISTORY_STORAGE_KEY = 'lfbot.memory.embedding.history.v1'
const EMBEDDING_HISTORY_FIELDS = [
  'embedding_model',
  'embedding_dimensions',
  'embedding_api_base',
  'embedding_timeout',
] as const

const EMBEDDING_DEFAULTS: Record<string, Partial<MemoryConfig>> = {
  local: {
    embedding_model: 'all-MiniLM-L6-v2',
    embedding_dimensions: 384,
    embedding_api_base: '',
    embedding_timeout: 30,
  },
  aliyun: {
    embedding_model: 'text-embedding-v4',
    embedding_dimensions: 1024,
    embedding_api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    embedding_timeout: 30,
  },
  openai_compatible: {
    embedding_model: 'text-embedding-3-small',
    embedding_dimensions: 1536,
    embedding_api_base: 'https://api.openai.com/v1',
    embedding_timeout: 30,
  },
}

const MemoryPage: React.FC = () => {
  const [configForm] = Form.useForm()
  const [roleplayMemoryForm] = Form.useForm()
  const [searchForm] = Form.useForm()
  const [addMemoryForm] = Form.useForm()

  // 时间格式化辅助函数
  const formatDateTime = (time: string | undefined | null): string => {
    if (!time) return '未知'
    try {
      const date = new Date(time)
      if (isNaN(date.getTime())) {
        return time
      }
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      })
    } catch {
      return time
    }
  }
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [activeTab, setActiveTab] = useState('config')
  const [config, setConfig] = useState<MemoryConfig | null>(null)
  const [stats, setStats] = useState<any>(null)
  const [shortTermMemories, setShortTermMemories] = useState<MemoryItem[]>([])
  const [pendingMemories, setPendingMemories] = useState<MemoryItem[]>([])
  const [midTermMemories, setMidTermMemories] = useState<MemorySummary[]>([])
  const [longTermMemories, setLongTermMemories] = useState<MemoryItem[]>([])
  const [searchResults, setSearchResults] = useState<MemoryItem[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [memoryUserOptions, setMemoryUserOptions] = useState<MemoryUserInfo[]>([])
  const [selectedUserId, setSelectedUserId] = useState<string>('')
  const [externalProfiles, setExternalProfiles] = useState<any[]>([])
  const [externalEvents, setExternalEvents] = useState<any[]>([])
  const [externalContext, setExternalContext] = useState<string>('')
  const [externalStatus, setExternalStatus] = useState<any>(null)
  const [externalLoading, setExternalLoading] = useState(false)
  const [externalQuery, setExternalQuery] = useState<string>('')
  const [externalLimit, setExternalLimit] = useState<number>(10)
  const [externalContextMaxTokens, setExternalContextMaxTokens] = useState<number>(500)
  const [externalContextTopics, setExternalContextTopics] = useState<string>('')

  const [saveStatus, setSaveStatus] = useState<{
    status: 'idle' | 'saving' | 'success' | 'warning' | 'error'
    message?: string
    detail?: string
    at?: string
  }>({ status: 'idle' })
  const [embeddingHistory, setEmbeddingHistory] = useState<Record<string, Partial<MemoryConfig>>>({})
  const embeddingSecretRef = useRef<Record<string, string | undefined>>({})
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [roleplayMemorySaving, setRoleplayMemorySaving] = useState(false)
  const [userConfig, setUserConfig] = useState<UserConfig | null>(null)
  const savedConfigRef = useRef<MemoryConfig | null>(null)

  // 配置标签页
  useEffect(() => {
    try {
      const raw = localStorage.getItem(EMBEDDING_HISTORY_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed && typeof parsed === 'object') {
          setEmbeddingHistory(parsed)
        }
      }
    } catch (error) {
      console.warn('加载嵌入历史失败:', error)
    }
  }, [])


  const loadMemoryUsers = async () => {
    try {
      const data = await memoryApi.getMemoryUsers()
      const ids = data.user_ids || []
      const infoList = Array.isArray(data.user_info) ? data.user_info : []
      setMemoryUserOptions(infoList)
      setSelectedUserId((prev) => {
        if (prev && ids.includes(prev)) return prev
        return ids[0] || ''
      })
    } catch (error) {
      console.error('加载记忆身份列表失败:', error)
    }
  }

  useEffect(() => {
    loadMemoryUsers()
  }, [])

  useEffect(() => {
    if (!selectedUserId) return
    searchForm.setFieldsValue({ user_id: selectedUserId })
    addMemoryForm.setFieldsValue({ user_id: selectedUserId })
  }, [selectedUserId, searchForm, addMemoryForm])

  useEffect(() => {
    if (activeTab === 'config') {
      loadConfig()
      loadStats()
    } else if (activeTab === 'short_term') {
      loadShortTermMemories()
    } else if (activeTab === 'pending') {
      loadPendingMemories()
    } else if (activeTab === 'mid_term') {
      loadMidTermMemories()
    } else if (activeTab === 'long_term') {
      loadLongTermMemories()
    } else if (activeTab === 'external') {
      loadExternalStatus()
      loadExternalProfiles()
      loadExternalEvents()
    }
  }, [activeTab])

  const updateEmbeddingHistory = (provider: string, snapshot: Partial<MemoryConfig>) => {
    if (!provider) return
    setEmbeddingHistory((prev) => {
      const next = { ...prev, [provider]: snapshot }
      try {
        localStorage.setItem(EMBEDDING_HISTORY_STORAGE_KEY, JSON.stringify(next))
      } catch (error) {
        console.warn('保存嵌入历史失败:', error)
      }
      return next
    })
  }

  const cacheEmbeddingConfig = (provider?: string) => {
    if (!provider) return
    const values = configForm.getFieldsValue([
      ...EMBEDDING_HISTORY_FIELDS,
      'embedding_api_key',
    ])
    const snapshot: Partial<MemoryConfig> = {
      embedding_model: values.embedding_model,
      embedding_dimensions: values.embedding_dimensions,
      embedding_api_base: values.embedding_api_base,
      embedding_timeout: values.embedding_timeout,
    }
    updateEmbeddingHistory(provider, snapshot)
    if (values.embedding_api_key !== undefined) {
      embeddingSecretRef.current[provider] = values.embedding_api_key
    }
  }

  const rememberEmbeddingFromConfig = (data: MemoryConfig) => {
    if (!data) return
    const provider = data.embedding_provider || 'local'
    const snapshot: Partial<MemoryConfig> = {
      embedding_model: data.embedding_model,
      embedding_dimensions: data.embedding_dimensions,
      embedding_api_base: data.embedding_api_base,
      embedding_timeout: data.embedding_timeout,
    }
    updateEmbeddingHistory(provider, snapshot)
    if (data.embedding_api_key !== undefined) {
      embeddingSecretRef.current[provider] = data.embedding_api_key
    }
  }

  const applyEmbeddingConfig = (provider: string) => {
    const cached = embeddingHistory[provider]
    const defaults = EMBEDDING_DEFAULTS[provider] || {}
    const nextFields: Partial<MemoryConfig> = { ...defaults, ...cached }
    const secret = embeddingSecretRef.current[provider]
    if (secret !== undefined) {
      nextFields.embedding_api_key = secret
    } else if (!cached?.embedding_api_key) {
      nextFields.embedding_api_key = ''
    }
    configForm.setFieldsValue({
      embedding_provider: provider,
      ...nextFields,
    })
  }

  const handleEmbeddingProviderChange = (nextProvider: string) => {
    const prevProvider = configForm.getFieldValue('embedding_provider')
    if (prevProvider && prevProvider !== nextProvider) {
      cacheEmbeddingConfig(prevProvider)
    }
    applyEmbeddingConfig(nextProvider)
  }

  const loadConfig = async () => {
    try {
      const [data, userCfg] = await Promise.all([
        memoryApi.getMemoryConfig(),
        userConfigApi.getConfig(),
      ])
      setConfig(data)
      setUserConfig(userCfg)
      savedConfigRef.current = data
      configForm.setFieldsValue(data)
      roleplayMemoryForm.setFieldsValue({
        short_term_max_rounds: 50,
        short_term_keep_rounds: 50,
        pending_enabled: true,
        pending_chunk_rounds: 20,
        pending_delete_after_summary: true,
        pending_overlap_messages: 4,
        mid_term_context_count: 3,
        summarizer_enabled: true,
        summarizer_llm: {
          provider: 'openai',
          model: '',
          api_base: '',
          api_key: '',
          temperature: 0.2,
          max_tokens: 1200,
        },
        summary_max_length: 500,
        max_summaries: 10,
        ...(userCfg.preferences?.roleplay_memory || {}),
        long_term_enabled: false,
        legacy_auto_extract_enabled: false,
      })
      if (Array.isArray(data?.external_memory_prefer_topics)) {
        setExternalContextTopics(data.external_memory_prefer_topics.join(','))
      }
      rememberEmbeddingFromConfig(data)
      setHasUnsavedChanges(false)
      return data
    } catch (error) {
      console.error('加载配置失败:', error)
      message.error('加载记忆配置失败，请检查后端服务')
      return null
    }
  }

  const loadStats = async () => {
    try {
      const data = await memoryApi.getMemoryStats()
      setStats(data)
    } catch (error) {
      console.error('加载记忆统计失败:', error)
    }
  }

  const handleSaveConfig = async () => {
    try {
      setLoading(true)
      setSaveStatus({
        status: 'saving',
        message: '正在保存...',
        at: new Date().toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }),
      })
      const values = await configForm.validateFields()

      // 保存前先缓存当前提供商的配置
      const currentProvider = values.embedding_provider
      if (currentProvider) {
        cacheEmbeddingConfig(currentProvider)
      }

      const result = await memoryApi.updateMemoryConfig(values)
      const savedConfig = await loadConfig()
      const savedAt = new Date().toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
      const successMessage = result?.message || '配置保存成功'
      setSaveStatus({
        status: 'success',
        message: successMessage,
        at: savedAt,
      })
      message.success(successMessage)
      setHasUnsavedChanges(false)

      if (savedConfig) {
        const mismatch =
          savedConfig.embedding_provider !== values.embedding_provider ||
          savedConfig.embedding_model !== values.embedding_model ||
          Number(savedConfig.embedding_dimensions || 0) !== Number(values.embedding_dimensions || 0)
        if (mismatch) {
          setSaveStatus({
            status: 'warning',
            message: '配置已保存但存在差异',
            detail: '后端返回的配置与提交的配置不一致',
            at: savedAt,
          })
          message.warning('配置已保存，但后端返回的配置与提交的配置不一致')
        }
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '未知错误'
      console.error('保存配置失败:', error)
      message.error(`保存配置失败: ${detail}`)
      setSaveStatus({
        status: 'error',
        message: '保存失败',
        detail,
        at: new Date().toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }),
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSaveRoleplayMemoryConfig = async () => {
    try {
      setRoleplayMemorySaving(true)
      const values = await roleplayMemoryForm.validateFields()
      const nextPreferences = {
        ...(userConfig?.preferences || {}),
        roleplay_memory: {
          ...values,
          short_term_enabled: true,
          mid_term_enabled: true,
          long_term_enabled: false,
          legacy_auto_extract_enabled: false,
        },
      }
      const updated = await userConfigApi.updateConfig({ preferences: nextPreferences })
      setUserConfig(updated)
      message.success('情景演绎记忆配置已保存')
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '未知错误'
      message.error(`保存情景记忆配置失败: ${detail}`)
      console.error(error)
    } finally {
      setRoleplayMemorySaving(false)
    }
  }

  const handleTestMemorySystem = async () => {
    try {
      setTesting(true)
      const result = await memoryApi.testMemorySystem()
      if (result.status === '正常') {
        message.success('记忆系统测试成功: ' + result.message)
      } else {
        message.warning('记忆系统测试异常: ' + result.message)
      }
      await loadStats()
    } catch (error) {
      message.error('记忆系统测试失败')
    } finally {
      setTesting(false)
    }
  }

  // 短期记忆标签页
  const loadShortTermMemories = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      const memories = await memoryApi.getShortTermMemories(selectedUserId, selectedUserId, 20)
      setShortTermMemories(memories || [])
    } catch (error) {
      console.error('加载短期记忆失败:', error)
      message.error('加载短期记忆失败')
    }
  }

  // 待处理区标签页
  const loadPendingMemories = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      const memories = await memoryApi.getPendingMemories(selectedUserId, selectedUserId, 200)
      setPendingMemories(memories || [])
    } catch (error) {
      console.error('加载待处理区失败:', error)
      message.error('加载待处理区失败')
    }
  }

  const handleSummarizePending = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      setLoading(true)
      const result = await memoryApi.summarizePendingMemories(selectedUserId, selectedUserId)
      if (result?.ok) {
        if (result?.processed) {
          const processedBatches = Number(result?.processed_batches || 0)
          if (processedBatches > 0) {
            message.success(`待处理区摘要完成（处理 ${processedBatches} 批）`)
          } else {
            message.success('已触发待处理区摘要')
          }
        } else {
          const recovered = Number(result?.recovered_pending_processing || 0)
          if (recovered > 0) {
            message.info(`已修复 ${recovered} 条异常处理中记录，请再次点击“立即摘要”`) 
          } else {
            message.info('已触发摘要，但当前待处理区为空或无需处理')
          }
        }
      } else {
        const reason = result?.reason
        const reasonText =
          reason === 'summarizer_disabled'
            ? '摘要LLM未启用'
            : reason === 'pipeline_disabled'
              ? '记忆流水线未启用'
            : '未知原因'
        message.info(`未触发摘要（${reasonText}）`)
      }
      await loadStats()
      await loadPendingMemories()
      await loadMidTermMemories()
      await loadLongTermMemories()
    } catch (error) {
      console.error('触发待处理区摘要失败:', error)
      message.error('触发待处理区摘要失败')
    } finally {
      setLoading(false)
    }
  }

  // 中期记忆标签页
  const loadMidTermMemories = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      const summaries = await memoryApi.getMidTermMemories(selectedUserId, undefined, 50)
      setMidTermMemories(summaries || [])
    } catch (error) {
      console.error('加载中期记忆失败:', error)
      message.error('加载中期记忆失败')
    }
  }

  // 长期记忆标签页
  const loadLongTermMemories = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      const memories = await memoryApi.getLongTermMemories(selectedUserId, 50)
      setLongTermMemories(memories || [])
    } catch (error) {
      console.error('加载长期记忆失败:', error)
      message.error('加载长期记忆失败')
    }
  }

  // 外部记忆标签页
  const loadExternalStatus = async () => {
    try {
      setExternalLoading(true)
      const data = await memoryApi.getExternalMemoryStatus()
      setExternalStatus(data)
    } catch (error) {
      console.error('加载外部记忆状态失败:', error)
      setExternalStatus(null)
    } finally {
      setExternalLoading(false)
    }
  }

  const loadExternalProfiles = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      setExternalLoading(true)
      const data = await memoryApi.getExternalMemoryProfiles(selectedUserId)
      setExternalProfiles(data || [])
    } catch (error) {
      console.error('加载外部画像失败:', error)
      message.error('加载外部画像失败')
    } finally {
      setExternalLoading(false)
    }
  }

  const loadExternalEvents = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      setExternalLoading(true)
      const data = await memoryApi.getExternalMemoryEvents(
        selectedUserId,
        externalLimit,
        externalQuery || undefined
      )
      setExternalEvents(data || [])
    } catch (error) {
      console.error('加载外部事件失败:', error)
      message.error('加载外部事件失败')
    } finally {
      setExternalLoading(false)
    }
  }

  const loadExternalContext = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      setExternalLoading(true)
      const topics = externalContextTopics
        .split(',')
        .map(item => item.trim())
        .filter(item => item.length > 0)
      const data = await memoryApi.getExternalMemoryContext(
        selectedUserId,
        externalContextMaxTokens,
        topics.length > 0 ? topics : undefined
      )
      setExternalContext(data || '')
    } catch (error) {
      console.error('加载外部上下文失败:', error)
      message.error('加载外部上下文失败')
    } finally {
      setExternalLoading(false)
    }
  }

  const handleSearchMemories = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    try {
      setSearchLoading(true)
      const values = await searchForm.validateFields()
      const results = await memoryApi.searchLongTermMemories(
        values.user_id || selectedUserId,
        values.query,
        values.top_k || 5,
        values.score_threshold || 0.5
      )
      setSearchResults(results || [])
      if (results.length === 0) {
        message.info('未找到相关记忆')
      }
    } catch (error) {
      console.error('搜索记忆失败:', error)
      message.error('搜索记忆失败')
    } finally {
      setSearchLoading(false)
    }
  }

  const handleAddMemory = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    if (config?.long_term_strategy === 'external') {
      message.warning('外部记忆暂不支持手动添加')
      return
    }
    try {
      const values = await addMemoryForm.validateFields()
      await memoryApi.addLongTermMemory(
        values.user_id || selectedUserId,
        values.content,
        values.importance || 0.5,
        values.metadata ? JSON.parse(values.metadata) : {}
      )
      message.success('长期记忆添加成功')
      addMemoryForm.resetFields()
      await loadLongTermMemories()
    } catch (error) {
      console.error('添加长期记忆失败:', error)
      message.error('添加长期记忆失败')
    }
  }

  const handleDeleteMemory = async (memoryId: string) => {
    if (config?.long_term_strategy === 'external') {
      message.warning('外部记忆暂不支持删除')
      return
    }
    try {
      await memoryApi.deleteLongTermMemory(memoryId)
      message.success('记忆删除成功')
      await loadLongTermMemories()
      // 如果当前在搜索结果中，也更新搜索结果
      if (searchResults.some(mem => mem.id === memoryId)) {
        setSearchResults(searchResults.filter(mem => mem.id !== memoryId))
      }
    } catch (error) {
      console.error('删除记忆失败:', error)
      message.error('删除记忆失败')
    }
  }

  const handleClearMemories = async () => {
    if (!selectedUserId) {
      message.warning('请选择记忆身份')
      return
    }
    if (config?.long_term_strategy === 'external') {
      message.warning('外部记忆暂不支持清除')
      return
    }
    try {
      await memoryApi.clearMemories(selectedUserId)
      message.success('记忆清除成功')
      setShortTermMemories([])
      setPendingMemories([])
      setMidTermMemories([])
      setLongTermMemories([])
      setSearchResults([])
    } catch (error) {
      console.error('清除记忆失败:', error)
      message.error('清除记忆失败')
    }
  }

  // 表格列定义
  const shortTermColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '角色',
      dataIndex: 'message',
      key: 'role',
      width: 80,
      render: (message: any) => {
        if (typeof message === 'string') {
          try {
            const parsed = JSON.parse(message)
            return parsed?.role || 'unknown'
          } catch {
            return 'unknown'
          }
        }
        return message?.role || 'unknown'
      },
    },
    {
      title: '内容',
      dataIndex: 'message',
      key: 'content',
      render: (message: any) => {
        if (typeof message === 'string') {
          try {
            const parsed = JSON.parse(message)
            return parsed?.content || '无内容'
          } catch {
            return message || '无内容'
          }
        }
        return message?.content || '无内容'
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => formatDateTime(time),
    },
  ]

  const pendingColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '角色',
      dataIndex: 'message',
      key: 'role',
      width: 80,
      render: (messageObj: any) => {
        const role = messageObj?.role || 'unknown'
        return <Tag color={role === 'user' ? 'blue' : role === 'assistant' ? 'green' : 'default'}>{role}</Tag>
      },
    },
    {
      title: '内容',
      dataIndex: 'message',
      key: 'content',
      render: (messageObj: any) => {
        const text = messageObj?.content || ''
        return (
          <Tooltip title={text}>
            <div style={{ maxWidth: 520, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {text || '无内容'}
            </div>
          </Tooltip>
        )
      },
    },
    {
      title: '索引',
      dataIndex: 'metadata',
      key: 'idx',
      width: 160,
      render: (metadata: any) => {
        const mi = metadata?.message_index ?? '-'
        const ri = metadata?.round_index ?? '-'
        return <span>m:{mi} / r:{ri}</span>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => formatDateTime(time),
    },
  ]

  const midTermColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '会话范围',
      dataIndex: 'conversation_range',
      key: 'conversation_range',
      width: 120,
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => formatDateTime(time),
    },
  ]

  const longTermColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
    },
    {
      title: '重要性',
      dataIndex: 'importance',
      key: 'importance',
      width: 100,
      render: (importance: number) => importance?.toFixed(2) || '0.50',
    },
    {
      title: '来源',
      dataIndex: ['metadata', 'source'],
      key: 'source',
      width: 100,
      render: (source: string) => source || 'unknown',
    },
    {
      title: '相似度',
      dataIndex: 'similarity',
      key: 'similarity',
      width: 100,
      render: (similarity: number) => similarity?.toFixed(3) || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => formatDateTime(time),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: MemoryItem) => (
        config?.long_term_strategy === 'external' ? (
          <Tag color="default">不可用</Tag>
        ) : (
          <Popconfirm
            title="确定要删除这条记忆吗？"
            onConfirm={() => handleDeleteMemory(record.id.toString())}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger size="small">
              删除
            </Button>
          </Popconfirm>
        )
      ),
    },
  ]

  const searchResultsColumns = [
    ...longTermColumns.slice(0, -1), // 不包括操作列
    {
      title: '相关度',
      dataIndex: 'similarity',
      key: 'similarity',
      width: 100,
      render: (similarity: number) => similarity ? (similarity * 100).toFixed(1) + '%' : 'N/A',
    },
  ]

  const externalProfileColumns = [
    {
      title: '主题',
      dataIndex: 'topic',
      key: 'topic',
      width: 120,
    },
    {
      title: '子主题',
      dataIndex: 'sub_topic',
      key: 'sub_topic',
      width: 120,
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => formatDateTime(time),
    },
  ]

  const externalEventColumns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => formatDateTime(time),
    },
    {
      title: '摘要',
      dataIndex: ['event_data', 'event_tip'],
      key: 'event_tip',
      render: (_: any, record: any) => record?.event_data?.event_tip || '无摘要',
    },
    {
      title: '标签',
      dataIndex: ['event_data', 'event_tags'],
      key: 'event_tags',
      width: 200,
      render: (_: any, record: any) => {
        const tags = record?.event_data?.event_tags
        if (!tags) return '-'
        if (Array.isArray(tags)) return tags.join(', ')
        if (typeof tags === 'object') return Object.entries(tags).map(([k, v]) => `${k}:${v}`).join(', ')
        return String(tags)
      },
    },
  ]

  return (
    <div style={{ padding: '0 24px' }}>
      <h1>记忆系统管理</h1>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <span>选择记忆身份:</span>
          <Select
            style={{ width: 420 }}
            value={selectedUserId}
            onChange={setSelectedUserId}
            options={memoryUserOptions.map(info => ({ label: info.display_name || info.user_id, value: info.user_id }))}
            placeholder="选择记忆身份"
            showSearch
            filterOption={(input, option) =>
              (option?.label as string || '').toLowerCase().includes(input.toLowerCase())
            }
          />
          <Button 
            icon={<ReloadOutlined />} 
            onClick={loadMemoryUsers}
          >
            刷新记忆身份
          </Button>
        </Space>
      </div>
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        {/* 配置标签页 */}
        <TabPane tab="配置" key="config">
          <Row gutter={[16, 16]}>
            <Col span={16}>
              <Card title="记忆系统配置" extra={
                <Space>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    loading={loading}
                    onClick={handleSaveConfig}
                    danger={hasUnsavedChanges}
                  >
                    {hasUnsavedChanges ? '保存配置 *' : '保存配置'}
                  </Button>
                  <Button
                    icon={<ExperimentOutlined />}
                    loading={testing}
                    onClick={handleTestMemorySystem}
                  >
                    测试系统
                  </Button>
                </Space>
              }>
                {saveStatus.status !== 'idle' ? (
                <Alert
                  type={
                    saveStatus.status === 'error'
                      ? 'error'
                      : saveStatus.status === 'warning'
                        ? 'warning'
                        : saveStatus.status === 'saving'
                          ? 'info'
                          : 'success'
                  }
                  showIcon
                  message={saveStatus.message || '未知状态'}
                  description={
                    saveStatus.detail || saveStatus.at ? (
                      <div>
                        {saveStatus.at ? <div>时间: {saveStatus.at}</div> : null}
                        {saveStatus.detail ? <div>详情: {saveStatus.detail}</div> : null}
                      </div>
                    ) : undefined
                  }
                  style={{ marginBottom: 12 }}
                />
              ) : null}

              {hasUnsavedChanges && saveStatus.status === 'idle' ? (
                <Alert
                  type="warning"
                  showIcon
                  message="有未保存的更改"
                  description="您已修改配置但尚未保存，请点击右上角的【保存配置】按钮保存更改。"
                  style={{ marginBottom: 12 }}
                />
              ) : null}

              <Form
                  form={configForm}
                  layout="vertical"
                  onValuesChange={() => {
                    setHasUnsavedChanges(true)
                    setSaveStatus({ status: 'idle' })
                  }}
                  initialValues={{
                    short_term_enabled: true,
                    mid_term_enabled: true,
                    mid_term_context_count: 3,
                    long_term_enabled: true,
                    long_term_strategy: 'local',
                    external_memory_provider: 'memobase',
                    external_memory_base_url: '',
                    external_memory_api_key: '',
                    external_memory_timeout: 30,
                    external_memory_prefer_topics: [],
                    embedding_provider: 'local',
                    embedding_model: 'all-MiniLM-L6-v2',
                    embedding_api_base: '',
                    embedding_api_key: '',
                    embedding_timeout: 30,
                    embedding_dimensions: 384,
                    rag_top_k: 3,
                    rag_score_threshold: 0.5,
                    short_term_max_rounds: 50,
                    short_term_keep_rounds: 50,
                    pending_enabled: true,
                    pending_chunk_rounds: 20,
                    pending_delete_after_summary: true,
                    pending_overlap_messages: 4,
                    summarizer_enabled: true,
                    summarizer_llm: {
                      provider: 'openai',
                      model: '',
                      api_base: '',
                      api_key: '',
                      temperature: 0.2,
                      max_tokens: 1200,
                    },
                    summarizer_max_facts: 20,
                    summarizer_fact_min_importance: null,
                    legacy_auto_extract_enabled: false,
                    summary_interval: 10,
                    summary_max_length: 500,
                    max_summaries: 10,
                    max_long_term_memories: 1000,
                  }}
                >
                  <Divider>流水线（短期→待处理→摘要→长期）</Divider>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="启用待处理区" name="pending_enabled" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item
                        label="摘要后删除原文"
                        name="pending_delete_after_summary"
                        valuePropName="checked"
                        tooltip="开启后：被摘要的待处理原文会被删除；关闭则转为archived归档。"
                      >
                        <Switch />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item
                        label="短期窗口保留轮次"
                        name="short_term_keep_rounds"
                        tooltip="1轮≈用户+助手各1条消息；为空则回退使用 short_term_max_rounds。"
                      >
                        <InputNumber min={1} max={200} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="待处理chunk轮次" name="pending_chunk_rounds">
                        <InputNumber min={1} max={200} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="摘要重叠消息数" name="pending_overlap_messages" tooltip="用于跨chunk衔接话题（建议2-6）。">
                        <InputNumber min={0} max={20} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Divider>摘要LLM（独立配置）</Divider>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="启用摘要LLM" name="summarizer_enabled" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="最多抽取事实条数" name="summarizer_max_facts">
                        <InputNumber min={0} max={200} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="事实入库重要度阈值" name="summarizer_fact_min_importance" tooltip="为空则回退使用 importance_threshold。">
                        <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item
                        label="提供商"
                        name={['summarizer_llm', 'provider']}
                        tooltip="摘要LLM独立配置；留空可回退使用全局 llm 配置"
                        dependencies={['summarizer_enabled']}
                        rules={[
                          ({ getFieldValue }) => ({
                            validator: async (_: any, value: any) => {
                              if (!getFieldValue('summarizer_enabled')) return
                              if (!value) throw new Error('请选择摘要LLM提供商')
                            },
                          }),
                        ]}
                      >
                        <Select
                          allowClear
                          options={[
                            { label: 'OpenAI', value: 'openai' },
                            { label: 'SiliconFlow', value: 'siliconflow' },
                            { label: 'DeepSeek', value: 'deepseek' },
                            { label: 'Yunwu', value: 'yunwu' },
                            { label: 'Qwen（DashScope）', value: 'qwen' },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item
                        label="模型"
                        name={['summarizer_llm', 'model']}
                        tooltip="摘要LLM独立配置；留空可回退使用全局 llm 配置"
                        dependencies={['summarizer_enabled']}
                        rules={[
                          ({ getFieldValue }) => ({
                            validator: async (_: any, value: any) => {
                              if (!getFieldValue('summarizer_enabled')) return
                              if (!value) throw new Error('请输入摘要LLM模型名')
                            },
                          }),
                        ]}
                      >
                        <Input placeholder="例如：gpt-4o-mini / deepseek-chat / gemini-3-flash-preview" />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="API Base" name={['summarizer_llm', 'api_base']}>
                        <Input placeholder="例如：https://api.openai.com/v1" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        label="API Key"
                        name={['summarizer_llm', 'api_key']}
                        dependencies={['summarizer_enabled']}
                        rules={[
                          ({ getFieldValue }) => ({
                            validator: async (_: any, value: any) => {
                              if (!getFieldValue('summarizer_enabled')) return
                              if (!value) throw new Error('请输入摘要LLM API Key')
                            },
                          }),
                        ]}
                      >
                        <Input.Password placeholder="sk-..." />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item label="Temperature" name={['summarizer_llm', 'temperature']}>
                        <InputNumber min={0} max={2} step={0.05} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item label="Max Tokens" name={['summarizer_llm', 'max_tokens']}>
                        <InputNumber min={16} max={8000} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item
                    label="保留旧启发式长期抽取"
                    name="legacy_auto_extract_enabled"
                    valuePropName="checked"
                    tooltip="不建议与摘要LLM同时开启；可能造成重复/污染长期记忆。"
                  >
                    <Switch />
                  </Form.Item>

                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="启用短期记忆" name="short_term_enabled" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="启用中期记忆" name="mid_term_enabled" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="启用长期记忆" name="long_term_enabled" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        label="长期记忆策略"
                        name="long_term_strategy"
                        tooltip="local=本地向量存储；external=外部记忆系统（Memobase）"
                      >
                        <Select
                          options={[
                            { label: '本地向量存储 (local)', value: 'local' },
                            { label: '外部记忆系统 (external)', value: 'external' },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item shouldUpdate noStyle>
                    {({ getFieldValue }) =>
                      getFieldValue('long_term_strategy') === 'external' ? (
                        <>
                          <Divider>外部记忆接入（Memobase）</Divider>
                          <Row gutter={16}>
                            <Col span={8}>
                              <Form.Item label="提供商" name="external_memory_provider">
                                <Select options={[{ label: 'Memobase', value: 'memobase' }]} />
                              </Form.Item>
                            </Col>
                            <Col span={8}>
                              <Form.Item label="服务地址" name="external_memory_base_url">
                                <Input placeholder="例如：http://localhost:8019" />
                              </Form.Item>
                            </Col>
                            <Col span={8}>
                              <Form.Item label="API Key" name="external_memory_api_key">
                                <Input.Password placeholder="secret" />
                              </Form.Item>
                            </Col>
                          </Row>
                          <Row gutter={16}>
                            <Col span={8}>
                              <Form.Item label="超时时间（秒）" name="external_memory_timeout">
                                <InputNumber min={5} max={120} style={{ width: '100%' }} />
                              </Form.Item>
                            </Col>
                            <Col span={16}>
                              <Form.Item
                                label="优先主题"
                                name="external_memory_prefer_topics"
                                tooltip="用于外部上下文获取时的优先主题列表"
                              >
                                <Select mode="tags" tokenSeparators={[',']} placeholder="例如：基本信息,兴趣爱好" />
                              </Form.Item>
                            </Col>
                          </Row>
                        </>
                      ) : null
                    }
                  </Form.Item>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item
                        label="中期摘要注入条数"
                        name="mid_term_context_count"
                        tooltip="将最近N条中期摘要注入到LLM上下文，0为不注入。"
                      >
                        <InputNumber min={0} max={50} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <Divider>向量存储设置</Divider>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item
                        label="嵌入提供商"
                        name="embedding_provider"
                        extra="切换提供商会自动填充历史配置"
                        tooltip="local=本地模型；aliyun=阿里云DashScope；openai_compatible=OpenAI兼容接口"
                      >
                        <Select
                          onChange={handleEmbeddingProviderChange}
                          options={[
                            { label: '本地模型 (local)', value: 'local' },
                            { label: '阿里云 DashScope (aliyun)', value: 'aliyun' },
                            { label: 'OpenAI兼容接口 (openai_compatible)', value: 'openai_compatible' },
                          ]}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="嵌入模型" name="embedding_model">
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="向量维度" name="embedding_dimensions">
                        <InputNumber min={32} max={4096} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="API Base" name="embedding_api_base">
                        <Input placeholder="例如：https://api.openai.com/v1" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="API Key" name="embedding_api_key">
                        <Input.Password placeholder="sk-..." />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="超时时间（秒）" name="embedding_timeout">
                        <InputNumber min={5} max={300} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="RAG返回数量 (top_k)" name="rag_top_k">
                        <InputNumber min={1} max={20} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="RAG分数阈值" name="rag_score_threshold">
                        <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <Divider>容量限制</Divider>
                  
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="短期记忆最大轮次" name="short_term_max_rounds">
                        <InputNumber min={10} max={200} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="摘要生成间隔" name="summary_interval">
                        <InputNumber min={5} max={50} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="摘要最大长度" name="summary_max_length">
                        <InputNumber min={100} max={2000} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="最大摘要数量" name="max_summaries">
                        <InputNumber min={1} max={50} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="长期记忆最大数量" name="max_long_term_memories">
                        <InputNumber min={100} max={5000} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>
              </Card>
            </Col>
            
            <Col span={8}>
              <Card title="系统统计">
                {stats ? (
                  <Descriptions column={1}>
                    <Descriptions.Item label="短期记忆状态">
                      {stats.short_term_enabled ? (
                        <Tag color="green">已启用</Tag>
                      ) : (
                        <Tag color="red">已禁用</Tag>
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="中期记忆状态">
                      {stats.mid_term_enabled ? (
                        <Tag color="green">已启用</Tag>
                      ) : (
                        <Tag color="red">已禁用</Tag>
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="长期记忆状态">
                      {stats.long_term_enabled ? (
                        <Tag color="green">已启用</Tag>
                      ) : (
                        <Tag color="red">已禁用</Tag>
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="系统类型">
                      <Tag color="green">{stats.system_type || '向量记忆系统'}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="短期记忆数量">
                      <Statistic value={stats.short_term_count || 0} />
                    </Descriptions.Item>
                    {"pending_count" in stats ? (
                      <Descriptions.Item label="待处理区数量">
                        <Statistic value={stats.pending_count || 0} />
                      </Descriptions.Item>
                    ) : null}
                    <Descriptions.Item label="摘要数量">
                      <Statistic value={stats.summary_count || 0} />
                    </Descriptions.Item>
                    <Descriptions.Item label="长期记忆数量">
                      <Statistic value={stats.long_term_count || 0} />
                    </Descriptions.Item>
                    <Descriptions.Item label="存储状态">
                      {stats.system_type === '外部记忆系统' ? (
                        <div>
                          <div>状态: {stats.external_memory_status?.ok ? '正常' : '异常'}</div>
                          <div>提供商: {stats.external_memory_status?.provider || '-'}</div>
                          <div>说明: {stats.external_memory_status?.reason || '-'}</div>
                        </div>
                      ) : typeof stats.vector_store_status === 'string' ? (
                        stats.vector_store_status
                      ) : (
                        <div>
                          <div>数量: {stats.vector_store_status?.count || 0}</div>
                          <div>状态: {stats.vector_store_status?.status || '未知'}</div>
                          <div>提供商: {stats.vector_store_status?.embedding_provider || '-'}</div>
                          <div>模型: {stats.vector_store_status?.embedding_model || '-'}</div>
                          <div>维度: {stats.vector_store_status?.embedding_dimensions || '-'}</div>
                        </div>
                      )}
                    </Descriptions.Item>
                  </Descriptions>
                ) : (
                  <div>加载中...</div>
                )}
                
                <Divider />
                
                <Alert
                  message="操作提示"
                  description={
                    <div>
                      <p>• 短期记忆: 保存当前对话的消息历史</p>
                      <p>• 待处理区: 超出短期窗口的原文，满chunk后会被摘要压缩</p>
                      <p>• 中期记忆: 自动生成的对话摘要</p>
                      <p>• 长期记忆: 重要信息的向量存储，支持检索</p>
                    </div>
                  }
                  type="info"
                  showIcon
                />
              </Card>
            </Col>
          </Row>

          <Card
            title="情景演绎记忆配置"
            style={{ marginTop: 16 }}
            extra={
              <Button
                type="primary"
                icon={<SaveOutlined />}
                loading={roleplayMemorySaving}
                onClick={handleSaveRoleplayMemoryConfig}
              >
                保存情景记忆配置
              </Button>
            }
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="情景演绎模式使用独立记忆"
              description="该配置只影响当前用户的情景演绎模式；长期记忆会被后端强制关闭，只保留短期记忆、待处理区和中期摘要。"
            />
            <Form
              form={roleplayMemoryForm}
              layout="vertical"
              initialValues={{
                short_term_max_rounds: 50,
                short_term_keep_rounds: 50,
                pending_enabled: true,
                pending_chunk_rounds: 20,
                pending_delete_after_summary: true,
                pending_overlap_messages: 4,
                mid_term_context_count: 3,
                summarizer_enabled: true,
                summarizer_llm: {
                  provider: 'openai',
                  model: '',
                  api_base: '',
                  api_key: '',
                  temperature: 0.2,
                  max_tokens: 1200,
                },
                summary_max_length: 500,
                max_summaries: 10,
              }}
            >
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="短期最大轮次" name="short_term_max_rounds">
                    <InputNumber min={2} max={500} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="短期保留轮次" name="short_term_keep_rounds">
                    <InputNumber min={2} max={500} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="注入摘要条数" name="mid_term_context_count">
                    <InputNumber min={0} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="最大摘要数量" name="max_summaries">
                    <InputNumber min={1} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="启用待处理区" name="pending_enabled" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="摘要后删除原文" name="pending_delete_after_summary" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="待处理触发轮次" name="pending_chunk_rounds">
                    <InputNumber min={1} max={200} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="摘要重叠消息数" name="pending_overlap_messages">
                    <InputNumber min={0} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="启用摘要LLM" name="summarizer_enabled" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="摘要最大长度" name="summary_max_length">
                    <InputNumber min={100} max={4000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="摘要模型提供商" name={['summarizer_llm', 'provider']}>
                    <Input placeholder="openai" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="摘要模型" name={['summarizer_llm', 'model']}>
                    <Input placeholder="使用全局默认或填写模型名" />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="摘要 API Base" name={['summarizer_llm', 'api_base']}>
                    <Input allowClear />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="摘要 API Key" name={['summarizer_llm', 'api_key']}>
                    <Input.Password allowClear />
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item label="温度" name={['summarizer_llm', 'temperature']}>
                    <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={4}>
                  <Form.Item label="最大Token" name={['summarizer_llm', 'max_tokens']}>
                    <InputNumber min={200} max={8000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </Card>
        </TabPane>
        
        {/* 短期记忆标签页 */}
        <TabPane tab="短期记忆" key="short_term">
          <Card 
            title="短期记忆（对话历史）" 
            extra={
              <Space>
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={loadShortTermMemories}
                >
                  刷新
                </Button>
                <Popconfirm
                  title="确定要清除所有短期记忆吗？"
                  onConfirm={handleClearMemories}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button icon={<DeleteOutlined />} danger>
                    清除所有记忆
                  </Button>
                </Popconfirm>
              </Space>
            }
          >
            <Table
              columns={shortTermColumns}
              dataSource={shortTermMemories}
              rowKey="id"
              pagination={{ pageSize: 10 }}
              loading={loading}
              size="small"
            />
          </Card>
        </TabPane>

        {/* 待处理区标签页 */}
        <TabPane tab="待处理区" key="pending">
          <Card
            title="待处理区（超出短期窗口的原文）"
            extra={
              <Space>
                <Button icon={<ReloadOutlined />} onClick={loadPendingMemories}>
                  刷新
                </Button>
                <Button type="primary" icon={<ExperimentOutlined />} loading={loading} onClick={handleSummarizePending}>
                  立即摘要
                </Button>
              </Space>
            }
          >
            <Alert
              type="info"
              showIcon
              message="提示"
              description="待处理区满一个chunk（配置项 pending_chunk_rounds）后才会生成摘要；点击“立即摘要”会强制汇总当前待处理内容（即使不足一个chunk）。"
              style={{ marginBottom: 12 }}
            />
            <Table
              columns={pendingColumns as any}
              dataSource={pendingMemories}
              rowKey="id"
              pagination={{ pageSize: 10 }}
              loading={loading}
              size="small"
            />
          </Card>
        </TabPane>
        
        {/* 中期记忆标签页 */}
        <TabPane tab="中期记忆" key="mid_term">
          <Card 
            title="中期记忆（对话摘要）" 
            extra={
              <Button 
                icon={<ReloadOutlined />} 
                onClick={loadMidTermMemories}
              >
                刷新
              </Button>
            }
          >
            <Table
              columns={midTermColumns}
              dataSource={midTermMemories}
              rowKey="id"
              pagination={{ pageSize: 10 }}
              loading={loading}
              size="small"
            />
          </Card>
        </TabPane>
        
        {/* 长期记忆标签页 */}
        <TabPane tab="长期记忆" key="long_term">
          <Row gutter={[16, 16]}>
            <Col span={16}>
              <Card 
                title="长期记忆（向量存储）" 
                extra={
                  <Space>
                    <Button 
                      icon={<ReloadOutlined />} 
                      onClick={loadLongTermMemories}
                    >
                      刷新
                    </Button>
                    <Popconfirm
                      title="确定要清除所有长期记忆吗？"
                      onConfirm={handleClearMemories}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button icon={<DeleteOutlined />} danger disabled={config?.long_term_strategy === 'external'}>
                        清除所有记忆
                      </Button>
                    </Popconfirm>
                  </Space>
                }
              >
                <Table
                  columns={longTermColumns}
                  dataSource={longTermMemories}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                  loading={loading}
                  size="small"
                />
              </Card>
            </Col>
            
            <Col span={8}>
              <Card title="搜索记忆">
                <Form form={searchForm} layout="vertical">
                  <Form.Item label="记忆身份" name="user_id" initialValue={selectedUserId}>
                    <Select
                      options={memoryUserOptions.map(info => ({ label: info.display_name || info.user_id, value: info.user_id }))}
                      placeholder="选择记忆身份"
                      showSearch
                      filterOption={(input, option) =>
                        (option?.label as string || '').toLowerCase().includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>
                  <Form.Item label="查询内容" name="query" rules={[{ required: true, message: '请输入查询内容' }]}>
                    <TextArea rows={3} />
                  </Form.Item>
                  <Row gutter={8}>
                    <Col span={12}>
                      <Form.Item label="返回数量" name="top_k" initialValue={5}>
                        <InputNumber min={1} max={20} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="分数阈值" name="score_threshold" initialValue={0.5}>
                        <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item>
                    <Button 
                      type="primary" 
                      icon={<SearchOutlined />} 
                      loading={searchLoading}
                      onClick={handleSearchMemories}
                      block
                    >
                      搜索
                    </Button>
                  </Form.Item>
                </Form>
                
                {searchResults.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <h4>搜索结果 ({searchResults.length} 条)</h4>
                    <Table
                      columns={searchResultsColumns}
                      dataSource={searchResults}
                      rowKey="id"
                      pagination={{ pageSize: 5 }}
                      size="small"
                    />
                  </div>
                )}
              </Card>
              
              <Card title="添加长期记忆" style={{ marginTop: 16 }}>
                <Form form={addMemoryForm} layout="vertical">
                  <Form.Item label="记忆身份" name="user_id" initialValue={selectedUserId}>
                    <Select
                      options={memoryUserOptions.map(info => ({ label: info.display_name || info.user_id, value: info.user_id }))}
                      placeholder="选择记忆身份"
                      showSearch
                      filterOption={(input, option) =>
                        (option?.label as string || '').toLowerCase().includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>
                  <Form.Item label="记忆内容" name="content" rules={[{ required: true, message: '请输入记忆内容' }]}>
                    <TextArea rows={4} />
                  </Form.Item>
                  <Form.Item label="重要性 (0-1)" name="importance" initialValue={0.5}>
                    <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item label="元数据 (JSON)" name="metadata">
                    <TextArea rows={2} placeholder='{"source": "manual", "tags": ["重要"]}' />
                  </Form.Item>
                  <Form.Item>
                    <Button 
                      type="primary" 
                      icon={<DatabaseOutlined />} 
                      onClick={handleAddMemory}
                      disabled={config?.long_term_strategy === 'external'}
                      block
                    >
                      添加记忆
                    </Button>
                  </Form.Item>
                </Form>
              </Card>
            </Col>
          </Row>
        </TabPane>

        {/* 外部记忆标签页 */}
        <TabPane tab="外部记忆" key="external">
          {config?.long_term_strategy !== 'external' ? (
            <Alert
              type="warning"
              showIcon
              message="当前未启用外部记忆策略"
              description="请在“配置”页将“长期记忆策略”切换为 external，并填写 Memobase 接入信息。"
              style={{ marginBottom: 16 }}
            />
          ) : null}
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card
                title="外部记忆状态"
                extra={
                  <Button icon={<ReloadOutlined />} onClick={loadExternalStatus} loading={externalLoading}>
                    刷新
                  </Button>
                }
              >
                {externalStatus ? (
                  <Space size="large">
                    <Tag color={externalStatus.ok ? 'green' : 'red'}>
                      {externalStatus.ok ? '连接正常' : '连接异常'}
                    </Tag>
                    <span>提供商: {externalStatus.provider || '-'}</span>
                    <span>原因: {externalStatus.reason || '-'}</span>
                  </Space>
                ) : (
                  <div>暂无状态</div>
                )}
              </Card>
            </Col>
          </Row>
          <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
            <Col span={12}>
              <Card
                title="用户画像（Profiles）"
                extra={
                  <Button icon={<ReloadOutlined />} onClick={loadExternalProfiles} loading={externalLoading}>
                    刷新
                  </Button>
                }
              >
                <Table
                  columns={externalProfileColumns as any}
                  dataSource={externalProfiles}
                  rowKey={(record: any) => record.id || `${record.topic}_${record.sub_topic}`}
                  pagination={{ pageSize: 10 }}
                  loading={externalLoading}
                  size="small"
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card
                title="用户事件（Events）"
                extra={
                  <Space>
                    <Input
                      placeholder="事件检索（可选）"
                      value={externalQuery}
                      onChange={(e) => setExternalQuery(e.target.value)}
                      style={{ width: 200 }}
                    />
                    <InputNumber
                      min={1}
                      max={50}
                      value={externalLimit}
                      onChange={(val) => setExternalLimit(Number(val || 10))}
                    />
                    <Button icon={<SearchOutlined />} onClick={loadExternalEvents} loading={externalLoading}>
                      搜索
                    </Button>
                  </Space>
                }
              >
                <Table
                  columns={externalEventColumns as any}
                  dataSource={externalEvents}
                  rowKey={(record: any) => record.id || record.created_at || Math.random().toString(36)}
                  pagination={{ pageSize: 8 }}
                  loading={externalLoading}
                  size="small"
                />
              </Card>
            </Col>
          </Row>
          <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
            <Col span={24}>
              <Card
                title="外部记忆上下文"
                extra={
                  <Space>
                    <InputNumber
                      min={50}
                      max={2000}
                      value={externalContextMaxTokens}
                      onChange={(val) => setExternalContextMaxTokens(Number(val || 500))}
                    />
                    <Input
                      placeholder="优先主题（逗号分隔）"
                      value={externalContextTopics}
                      onChange={(e) => setExternalContextTopics(e.target.value)}
                      style={{ width: 260 }}
                    />
                    <Button icon={<EyeOutlined />} onClick={loadExternalContext} loading={externalLoading}>
                      获取上下文
                    </Button>
                  </Space>
                }
              >
                <TextArea rows={8} value={externalContext} readOnly />
              </Card>
            </Col>
          </Row>
        </TabPane>
      </Tabs>
    </div>
  )
}

export default MemoryPage
