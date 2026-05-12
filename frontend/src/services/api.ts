import axios from 'axios'
import {
  ASRConfig,
  SystemConfig,
  TTSConfig,
  VoiceCharacter,
  PromptEnhancerConfig,
  PromptEnhancePreview,
  DailyHabitsConfig,
  DailyHabitsStatus,
  EmoteConfig,
  EmoteConfigResponse,
  EmoteCategoryInfo,
  CerebellumState,
  CerebellumMotivation,
  CerebellumHistoryItem,
  DailyScheduleGenConfig,
  GeneratedScheduleStatus,
  GeneratedScheduleData,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 请求拦截器：自动添加 Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：处理 401 错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期或无效，清除本地存储并跳转登录页
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // 如果不在登录页，则跳转
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// 获取当前用户ID的辅助函数
const getCurrentUserId = (): string => {
  try {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      const user = JSON.parse(userStr)
      return String(user.id)
    }
  } catch (e) {
    console.error('获取用户ID失败:', e)
  }
  return 'web_user'
}

export const configApi = {
  // 获取系统配置
  getConfig: async (): Promise<SystemConfig> => {
    try {
      console.log('请求配置API: /api/config')
      const response = await api.get('/config')
      console.log('API响应:', response.data)
      return response.data
    } catch (error: any) {
      console.error('配置API错误:', error)
      if (error.response) {
        console.error('响应状态:', error.response.status)
        console.error('响应数据:', error.response.data)
      }
      throw error
    }
  },

  // 更新系统配置
  updateConfig: async (config: SystemConfig): Promise<void> => {
    try {
      console.log('更新配置:', config)
      const response = await api.post('/config', config)
      console.log('更新响应:', response.data)
    } catch (error: any) {
      console.error('更新配置错误:', error)
      if (error.response) {
        console.error('响应状态:', error.response.status)
        console.error('响应数据:', error.response.data)
      }
      throw error
    }
  },

  // 测试LLM连接
  testLLMConnection: async (): Promise<boolean> => {
    try {
      console.log('测试LLM连接...')
      const response = await api.post('/test-llm')
      console.log('测试结果:', response.data)
      return response.data.success
    } catch (error: any) {
      console.error('LLM测试错误:', error)
      return false
    }
  },
}

export const chatApi = {
  // 发送聊天消息
  sendMessage: async (message: string, userId?: string): Promise<string> => {
    const response = await api.post('/chat', {
      message,
      user_id: userId || getCurrentUserId()
    })
    return response.data.response
  },

  // 流式聊天
  streamChat: async (message: string, userId?: string) => {
    const token = localStorage.getItem('token')
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message,
        user_id: userId || getCurrentUserId()
      }),
    })
    
    if (!response.ok) {
      throw new Error('Stream chat failed')
    }
    
    return response
  },
}

export const ttsApi = {
  // 获取TTS配置
  getTTSConfig: async (): Promise<TTSConfig> => {
    try {
      const response = await api.get('/tts/config')
      return response.data.data
    } catch (error: any) {
      console.error('获取TTS配置错误:', error)
      throw error
    }
  },

  // 更新TTS配置
  updateTTSConfig: async (config: Partial<TTSConfig>): Promise<void> => {
    try {
      const response = await api.post('/tts/config', config)
      console.log('TTS配置更新成功:', response.data)
    } catch (error: any) {
      console.error('更新TTS配置错误:', error)
      throw error
    }
  },

  // 获取语音角色列表
  getVoices: async (): Promise<VoiceCharacter[]> => {
    try {
      const response = await api.get('/tts/voices')
      return response.data.data
    } catch (error: any) {
      console.error('获取语音角色列表错误:', error)
      throw error
    }
  },

  // 合成语音
  synthesize: async (text: string, voice?: string): Promise<Blob> => {
    try {
      const response = await api.post('/tts/synthesize', {
        text,
        voice
      }, {
        responseType: 'blob'
      })
      return response.data
    } catch (error: any) {
      console.error('语音合成错误:', error)
      throw error
    }
  },

  // 测试TTS连接
  testTTSConnection: async (): Promise<boolean> => {
    try {
      const response = await api.post('/tts/test')
      return response.data.success
    } catch (error: any) {
      console.error('TTS连接测试错误:', error)
      return false
    }
  },

  // 千问：上传声音复刻样本并创建/更新音色
  qwenVoiceClone: async (params: {
    file: File
    activate?: boolean
    languageHints?: string
    apiKey?: string
    model?: string
    preferredName?: string
    customizationUrl?: string
    realtimeWsUrl?: string
  }): Promise<any> => {
    const formData = new FormData()
    formData.append('file', params.file)
    formData.append('activate', String(params.activate ?? true))
    if (params.languageHints) {
      formData.append('language_hints', params.languageHints)
    }
    if (params.apiKey) formData.append('api_key', params.apiKey)
    if (params.model) formData.append('model', params.model)
    if (params.preferredName) formData.append('preferred_name', params.preferredName)
    if (params.customizationUrl) formData.append('customization_url', params.customizationUrl)
    if (params.realtimeWsUrl) formData.append('realtime_ws_url', params.realtimeWsUrl)
    const response = await api.post('/tts/qwen/voice-clone', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data.data
  },
}

export const asrApi = {
  getASRConfig: async (): Promise<ASRConfig> => {
    try {
      const response = await api.get('/asr/config')
      return response.data.data
    } catch (error: any) {
      console.error('获取ASR配置错误:', error)
      throw error
    }
  },

  updateASRConfig: async (config: Partial<ASRConfig>): Promise<void> => {
    try {
      const response = await api.post('/asr/config', config)
      console.log('ASR配置更新成功:', response.data)
    } catch (error: any) {
      console.error('更新ASR配置错误:', error)
      throw error
    }
  },

  testASRConnection: async (): Promise<boolean> => {
    try {
      const response = await api.post('/asr/test')
      return response.data.success
    } catch (error: any) {
      console.error('ASR连接测试错误:', error)
      return false
    }
  }
}

export const imageGenApi = {
  // 获取图像生成配置
  getImageGenConfig: async (): Promise<any> => {
    try {
      const response = await api.get('/image-gen/config')
      return response.data.data
    } catch (error: any) {
      console.error('获取图像生成配置错误:', error)
      throw error
    }
  },

  // 更新图像生成配置
  updateImageGenConfig: async (config: any): Promise<void> => {
    try {
      const response = await api.post('/image-gen/config', config)
      console.log('图像生成配置更新成功:', response.data)
    } catch (error: any) {
      console.error('更新图像生成配置错误:', error)
      throw error
    }
  },

  // 生成图像
  generateImage: async (prompt: string): Promise<{ success: boolean; message: string; image_data?: string }> => {
    try {
      const response = await api.post('/image-gen/generate', {
        prompt
      })
      return response.data
    } catch (error: any) {
      console.error('图像生成错误:', error)
      throw error
    }
  },

  // 测试图像生成连接
  testImageGenConnection: async (): Promise<boolean> => {
    try {
      const response = await api.post('/image-gen/test-connection')
      return response.data.success
    } catch (error: any) {
      console.error('图像生成连接测试错误:', error)
      return false
    }
  },
}

export const visionApi = {
  // 获取视觉识别配置
  getVisionConfig: async (): Promise<any> => {
    try {
      const response = await api.get('/vision/config')
      return response.data.data
    } catch (error: any) {
      console.error('获取视觉识别配置错误:', error)
      throw error
    }
  },

  // 更新视觉识别配置
  updateVisionConfig: async (config: any): Promise<void> => {
    try {
      const response = await api.post('/vision/config', config)
      console.log('视觉识别配置更新成功:', response.data)
    } catch (error: any) {
      console.error('更新视觉识别配置错误:', error)
      throw error
    }
  },

  // 测试视觉识别连接
  testVisionConnection: async (): Promise<boolean> => {
    try {
      const response = await api.post('/vision/test-connection')
      return response.data.success
    } catch (error: any) {
      console.error('视觉识别连接测试错误:', error)
      return false
    }
  },

  // 识别图片
  recognizeImage: async (imageUrl?: string, imageData?: string, prompt?: string): Promise<{ success: boolean; message: string; recognition_text?: string }> => {
    try {
      const response = await api.post('/vision/recognize', {
        image_url: imageUrl,
        image_data: imageData,
        prompt
      })
      return response.data
    } catch (error: any) {
      console.error('图片识别错误:', error)
      throw error
    }
  },
}

export const memoryApi = {
  // 获取记忆配置
  getMemoryConfig: async (): Promise<any> => {
    try {
      const response = await api.get('/memory/config')
      return response.data.config
    } catch (error: any) {
      console.error('获取记忆配置错误:', error)
      throw error
    }
  },

  // 更新记忆配置
  updateMemoryConfig: async (config: any): Promise<any> => {
    try {
      const response = await api.post('/memory/config', { config })
      console.log('????????:', response.data)
      return response.data
    } catch (error: any) {
      console.error('????????:', error)
      throw error
    }
  },

  // 获取记忆统计信息
  getMemoryStats: async (): Promise<any> => {
    try {
      const response = await api.get('/memory/stats')
      return response.data
    } catch (error: any) {
      console.error('获取记忆统计错误:', error)
      throw error
    }
  },

  // 获取短期记忆
  getShortTermMemories: async (user_id: string, session_id: string, limit: number = 50): Promise<any> => {
    try {
      const response = await api.get('/memory/short-term', {
        params: { user_id, session_id, limit }
      })
      return response.data.memories
    } catch (error: any) {
      console.error('获取短期记忆错误:', error)
      throw error
    }
  },

  // 获取待处理区原文
  getPendingMemories: async (user_id: string, session_id: string, limit: number = 100): Promise<any> => {
    try {
      const response = await api.get('/memory/pending', {
        params: { user_id, session_id, limit }
      })
      return response.data.memories
    } catch (error: any) {
      console.error('获取待处理区错误:', error)
      throw error
    }
  },

  // 手动触发：摘要待处理区
  summarizePendingMemories: async (user_id: string, session_id: string): Promise<any> => {
    try {
      const response = await api.post('/memory/pending/summarize', null, {
        params: { user_id, session_id }
      })
      return response.data
    } catch (error: any) {
      console.error('触发待处理区摘要错误:', error)
      throw error
    }
  },

  // 获取中期记忆（摘要）
  getMidTermMemories: async (user_id: string, session_id?: string, limit: number = 10): Promise<any> => {
    try {
      const params: any = { user_id, limit }
      if (session_id) params.session_id = session_id
      const response = await api.get('/memory/mid-term', { params })
      return response.data.summaries
    } catch (error: any) {
      console.error('获取中期记忆错误:', error)
      throw error
    }
  },

  // 获取长期记忆
  getLongTermMemories: async (user_id: string, limit: number = 100): Promise<any> => {
    try {
      const response = await api.get('/memory/long-term', {
        params: { user_id, limit }
      })
      return response.data.memories
    } catch (error: any) {
      console.error('获取长期记忆错误:', error)
      throw error
    }
  },

  // 搜索长期记忆
  searchLongTermMemories: async (user_id: string, query: string, top_k: number = 3, score_threshold: number = 0.5): Promise<any> => {
    try {
      const response = await api.post('/memory/long-term/search', {
        user_id,
        query,
        top_k,
        score_threshold
      })
      return response.data.memories
    } catch (error: any) {
      console.error('搜索长期记忆错误:', error)
      throw error
    }
  },

  // 添加长期记忆
  addLongTermMemory: async (user_id: string, content: string, importance: number = 0.5, metadata: any = {}): Promise<void> => {
    try {
      const response = await api.post('/memory/long-term', {
        user_id,
        content,
        importance,
        metadata
      })
      console.log('添加长期记忆成功:', response.data)
    } catch (error: any) {
      console.error('添加长期记忆错误:', error)
      throw error
    }
  },

  // 删除长期记忆
  deleteLongTermMemory: async (memory_id: string): Promise<void> => {
    try {
      const response = await api.delete(`/memory/long-term/${memory_id}`)
      console.log('删除记忆成功:', response.data)
    } catch (error: any) {
      console.error('删除长期记忆错误:', error)
      throw error
    }
  },

  // 更新长期记忆
  updateLongTermMemory: async (memory_id: string, content?: string, importance?: number, metadata?: any): Promise<void> => {
    try {
      const response = await api.put(`/memory/long-term/${memory_id}`, {
        content,
        importance,
        metadata
      })
      console.log('更新记忆成功:', response.data)
    } catch (error: any) {
      console.error('更新长期记忆错误:', error)
      throw error
    }
  },

  // 清除记忆
  clearMemories: async (user_id: string, session_id?: string): Promise<void> => {
    try {
      const response = await api.post('/memory/clear', {
        user_id,
        session_id
      })
      console.log('清除记忆成功:', response.data)
    } catch (error: any) {
      console.error('清除记忆错误:', error)
      throw error
    }
  },

  // 获取用户ID列表
  getMemoryUsers: async (): Promise<{ user_ids: string[] }> => {
    try {
      const response = await api.get('/memory/users')
      return response.data
    } catch (error: any) {
      console.error('获取用户ID列表错误:', error)
      throw error
    }
  },

  // 测试记忆系统
  testMemorySystem: async (): Promise<any> => {
    try {
      const response = await api.get('/memory/test')
      return response.data
    } catch (error: any) {
      console.error('测试记忆系统错误:', error)
      throw error
    }
  },

  // 外部记忆状态
  getExternalMemoryStatus: async (): Promise<any> => {
    try {
      const response = await api.get('/memory/external/ping')
      return response.data
    } catch (error: any) {
      console.error('获取外部记忆状态错误:', error)
      throw error
    }
  },

  // 外部记忆画像
  getExternalMemoryProfiles: async (user_id: string): Promise<any> => {
    try {
      const response = await api.get('/memory/external/profiles', { params: { user_id } })
      return response.data.profiles
    } catch (error: any) {
      console.error('获取外部记忆画像错误:', error)
      throw error
    }
  },

  // 外部记忆事件
  getExternalMemoryEvents: async (user_id: string, limit: number = 10, query?: string): Promise<any> => {
    try {
      const response = await api.get('/memory/external/events', {
        params: { user_id, limit, query }
      })
      return response.data.events
    } catch (error: any) {
      console.error('获取外部记忆事件错误:', error)
      throw error
    }
  },

  // 外部记忆上下文
  getExternalMemoryContext: async (
    user_id: string,
    max_token_size: number = 500,
    prefer_topics?: string[]
  ): Promise<any> => {
    try {
      const response = await api.post('/memory/external/context', {
        user_id,
        max_token_size,
        prefer_topics
      })
      return response.data.context
    } catch (error: any) {
      console.error('获取外部记忆上下文错误:', error)
      throw error
    }
  },
}

export const proactiveApi = {
  getConfig: async (): Promise<any> => {
    const response = await api.get('/proactive/config')
    return response.data.config
  },
  updateConfig: async (cfg: any): Promise<void> => {
    await api.post('/proactive/config', cfg)
  },
  getStatus: async (): Promise<any> => {
    const response = await api.get('/proactive/status')
    return response.data
  },
  triggerOnce: async (payload: { channel: string; user_id: string; session_id?: string; display_name?: string; instruction?: string; }): Promise<string> => {
    const response = await api.post('/proactive/trigger', payload)
    return response.data.message
  },
  pollMessages: async (params: { channel: string; user_id: string; session_id?: string; limit?: number }): Promise<any[]> => {
    const response = await api.get('/proactive/messages', { params })
    return response.data.messages || []
  }
}

export const promptEnhancerApi = {
  getConfig: async (): Promise<PromptEnhancerConfig> => {
    const response = await api.get('/prompt-enhancer/config')
    return response.data
  },
  updateConfig: async (updates: Partial<PromptEnhancerConfig>): Promise<PromptEnhancerConfig> => {
    const response = await api.put('/prompt-enhancer/config', updates)
    return response.data.config
  },
  preview: async (prompt: string, forceCategories?: string[]): Promise<PromptEnhancePreview> => {
    const response = await api.post('/prompt-enhancer/preview', {
      prompt,
      force_categories: forceCategories
    })
    return response.data
  },
  getWordBanks: async (): Promise<any> => {
    const response = await api.get('/prompt-enhancer/word-banks')
    return response.data
  },
  reloadWordBanks: async (): Promise<void> => {
    await api.post('/prompt-enhancer/word-banks/reload')
  },
  addCustomWords: async (category: string, words: string[]): Promise<any> => {
    const response = await api.post('/prompt-enhancer/word-banks/custom', { category, words })
    return response.data
  },
  deleteCustomWords: async (category: string, words?: string[]): Promise<any> => {
    const response = await api.delete('/prompt-enhancer/word-banks/custom', { 
      data: { category, words } 
    })
    return response.data
  }
}

export const emoteApi = {
  getConfig: async (): Promise<EmoteConfigResponse> => {
    const response = await api.get('/emotes/config')
    return response.data
  },
  updateConfig: async (config: EmoteConfig): Promise<EmoteConfigResponse> => {
    const response = await api.post('/emotes/config', config)
    return response.data
  },
  reloadFiles: async (): Promise<{ success: boolean; categories: EmoteCategoryInfo[]; base_path: string }> => {
    const response = await api.post('/emotes/reload')
    return response.data
  }
}

export const dailyHabitsApi = {
  getConfig: async (): Promise<DailyHabitsConfig> => {
    const response = await api.get('/mcp/daily-habits/config')
    return response.data.config
  },
  saveConfig: async (config: DailyHabitsConfig): Promise<void> => {
    await api.post('/mcp/daily-habits/config', config)
  },
  getStatus: async (): Promise<DailyHabitsStatus> => {
    const response = await api.get('/mcp/daily-habits/status')
    return response.data
  },
}

export const dailyScheduleApi = {
  getStatus: async (): Promise<GeneratedScheduleStatus> => {
    const response = await api.get('/daily-schedule/status')
    return response.data
  },
  getToday: async (): Promise<GeneratedScheduleData> => {
    const response = await api.get('/daily-schedule/today')
    return response.data
  },
  generate: async (force = false): Promise<{ success: boolean; message: string; slot_count: number; generated_at: string | null }> => {
    const response = await api.post('/daily-schedule/generate', { force })
    return response.data
  },
  getConfig: async (): Promise<DailyScheduleGenConfig> => {
    const response = await api.get('/config')
    const raw = response.data?.daily_schedule_generation || {}
    return {
      enabled: raw.enabled ?? true,
      generate_window_start: raw.generate_window_start ?? '00:00',
      generate_window_end: raw.generate_window_end ?? '06:00',
      persona_name: raw.persona_name ?? '',
      persona_desc: raw.persona_desc ?? '',
      prompt_template: raw.prompt_template ?? '',
      timezone: raw.timezone ?? '',
      llm: raw.llm ?? null,
    }
  },
  saveConfig: async (cfg: DailyScheduleGenConfig): Promise<void> => {
    // 通过全局 config 接口保存 daily_schedule_generation 节
    await api.post('/config', { daily_schedule_generation: cfg })
  },
}

export const reminderApi = {
  getConfig: async (): Promise<any> => {
    const response = await api.get('/reminder/config')
    return response.data
  },
  updateConfig: async (config: any): Promise<any> => {
    const response = await api.post('/reminder/config', config)
    return response.data
  },
  getReminderList: async (params?: { user_id?: string; session_id?: string; status?: string; limit?: number }): Promise<any> => {
    const response = await api.get('/reminder/list', { params })
    return response.data
  },
  createReminder: async (data: {
    user_id: string
    session_id: string
    content: string
    trigger_time: string
    original_message?: string
    time_expression?: string
    reminder_message?: string
    metadata?: any
  }): Promise<any> => {
    const response = await api.post('/reminder/create', data)
    return response.data
  },
  reminderAction: async (reminderId: number, action: 'complete' | 'cancel'): Promise<any> => {
    const response = await api.post(`/reminder/${reminderId}/action`, { action })
    return response.data
  },
  getPendingReminders: async (): Promise<any> => {
    const response = await api.get('/reminder/pending')
    return response.data
  },
}

export const cerebellumApi = {
  getState: async (): Promise<{
    enabled: boolean
    running: boolean
    state: CerebellumState
    config: any
    motivation_count: number
  }> => {
    const response = await api.get('/cerebellum/state')
    return response.data
  },
  getMotivations: async (): Promise<CerebellumMotivation[]> => {
    const response = await api.get('/cerebellum/motivation')
    return response.data.motivations || []
  },
  getHistory: async (hours = 24, limit = 500): Promise<CerebellumHistoryItem[]> => {
    const response = await api.get('/cerebellum/history', { params: { hours, limit } })
    return response.data.history || []
  },
  getConfig: async (): Promise<any> => {
    const response = await api.get('/cerebellum/config')
    return response.data.config
  },
  updateConfig: async (config: any): Promise<any> => {
    const response = await api.post('/cerebellum/config', config)
    return response.data
  },
  submitStimulus: async (payload: any): Promise<any> => {
    const response = await api.post('/cerebellum/stimulus', payload)
    return response.data
  },
}

// 用户配置 API（用户个人配置，与全局配置分离）
export interface UserConfig {
  system_prompt?: string
  llm?: Record<string, any>
  tts?: Record<string, any>
  image_generation?: Record<string, any>
  vision?: Record<string, any>
  prompt_enhancer?: Record<string, any>
  emotes?: Record<string, any>
  proactive_chat?: Record<string, any>
  preferences?: Record<string, any>
}

export const userConfigApi = {
  // 获取当前用户的配置
  getConfig: async (): Promise<UserConfig> => {
    const response = await api.get('/user/config')
    return response.data
  },

  // 更新当前用户的配置
  updateConfig: async (config: Partial<UserConfig>): Promise<UserConfig> => {
    const response = await api.put('/user/config', config)
    return response.data
  },

  // 重置用户配置（恢复使用全局默认配置）
  resetConfig: async (configType?: string): Promise<void> => {
    const params = configType ? { config_type: configType } : {}
    await api.delete('/user/config', { params })
  },

  // 获取用户完整信息（包括配置）
  getProfile: async (): Promise<any> => {
    const response = await api.get('/user/profile')
    return response.data
  },
}

// 用户认证 API
export const authApi = {
  // 登录
  login: async (username: string, password: string): Promise<{ access_token: string; user: any }> => {
    const response = await api.post('/auth/login', { username, password })
    return response.data
  },

  // 注册
  register: async (data: {
    username: string
    password: string
    nickname?: string
    qq_user_id?: string
  }): Promise<any> => {
    const response = await api.post('/auth/register', data)
    return response.data
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<any> => {
    const response = await api.get('/auth/me')
    return response.data
  },

  // 修改密码
  changePassword: async (oldPassword: string, newPassword: string): Promise<void> => {
    await api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
}

// 管理员 API
export const adminApi = {
  // 获取所有用户列表
  getUsers: async (): Promise<any[]> => {
    const response = await api.get('/admin/users')
    return response.data.users
  },

  // 获取指定用户的配置
  getUserConfig: async (userKey: string): Promise<any> => {
    const response = await api.get(`/admin/users/${userKey}/config`)
    return response.data
  },

  // 更新指定用户的配置
  updateUserConfig: async (userKey: string, config: any): Promise<any> => {
    const response = await api.put(`/admin/users/${userKey}/config`, config)
    return response.data
  },

  // 创建/更新 QQ 用户
  upsertQQUser: async (data: { qq_user_id: string; nickname?: string; avatar?: string }): Promise<any> => {
    const response = await api.post('/admin/users/qq', data)
    return response.data
  },

  // 删除用户
  deleteUser: async (userId: number): Promise<void> => {
    await api.delete(`/admin/users/${userId}`)
  },

  // 设置用户管理员状态
  setUserAdmin: async (userId: number, isAdmin: boolean): Promise<void> => {
    await api.post(`/admin/users/${userId}/admin`, { is_admin: isAdmin ? 1 : 0 })
  },
}

export default api
