/**
 * 配置代理服务
 * 
 * 根据用户角色自动切换配置读写目标：
 * - 管理员：读写全局配置（影响所有人的默认值）
 * - 普通用户：读写自己的用户配置（覆盖全局默认值）
 * 
 * 这样各配置页面无需修改，只需要把 API 调用替换为代理即可。
 */
import api from './api'
import { userConfigApi } from './api'

/**
 * 判断当前用户是否为管理员
 */
function isCurrentUserAdmin(): boolean {
  try {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      const user = JSON.parse(userStr)
      return user.is_admin === 1
    }
  } catch (e) {
    // ignore
  }
  return false
}

/**
 * 配置代理 - TTS
 * 管理员：读写全局 /api/tts/config
 * 普通用户：读写用户配置中的 tts 字段
 */
export const ttsConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/tts/config')
      return response.data.data
    } else {
      // 先获取用户配置，如果有则返回，否则返回全局配置作为展示
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.tts && Object.keys(userConfig.tts).length > 0) {
        return userConfig.tts
      }
      // 没有用户配置，返回全局配置供展示
      const response = await api.get('/tts/config')
      return response.data.data
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.post('/tts/config', config)
      return response.data
    } else {
      // 普通用户保存到自己的配置
      await userConfigApi.updateConfig({ tts: config })
    }
  },
}

/**
 * 配置代理 - ASR
 */
export const asrConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/asr/config')
      return response.data.data
    } else {
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.preferences?.asr && Object.keys(userConfig.preferences.asr).length > 0) {
        return userConfig.preferences.asr
      }
      const response = await api.get('/asr/config')
      return response.data.data
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.post('/asr/config', config)
      return response.data
    } else {
      const currentConfig = await userConfigApi.getConfig()
      await userConfigApi.updateConfig({
        preferences: { ...(currentConfig.preferences || {}), asr: config }
      })
    }
  },
}

/**
 * 配置代理 - 图像生成
 */
export const imageGenConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/image-gen/config')
      return response.data.data
    } else {
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.image_generation && Object.keys(userConfig.image_generation).length > 0) {
        return userConfig.image_generation
      }
      const response = await api.get('/image-gen/config')
      return response.data.data
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.post('/image-gen/config', config)
      return response.data
    } else {
      await userConfigApi.updateConfig({ image_generation: config })
    }
  },
}

/**
 * 配置代理 - 视觉识别
 */
export const visionConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/vision/config')
      return response.data.data
    } else {
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.vision && Object.keys(userConfig.vision).length > 0) {
        return userConfig.vision
      }
      const response = await api.get('/vision/config')
      return response.data.data
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.post('/vision/config', config)
      return response.data
    } else {
      await userConfigApi.updateConfig({ vision: config })
    }
  },
}

/**
 * 配置代理 - 提示词增强
 */
export const promptEnhancerConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/prompt-enhancer/config')
      return response.data
    } else {
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.prompt_enhancer && Object.keys(userConfig.prompt_enhancer).length > 0) {
        return userConfig.prompt_enhancer
      }
      const response = await api.get('/prompt-enhancer/config')
      return response.data
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.put('/prompt-enhancer/config', config)
      return response.data
    } else {
      await userConfigApi.updateConfig({ prompt_enhancer: config })
    }
  },
}

/**
 * 配置代理 - 表情包
 */
export const emoteConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/emotes/config')
      return response.data
    } else {
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.emotes && Object.keys(userConfig.emotes).length > 0) {
        return userConfig.emotes
      }
      const response = await api.get('/emotes/config')
      return response.data
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.post('/emotes/config', config)
      return response.data
    } else {
      await userConfigApi.updateConfig({ emotes: config })
    }
  },
}

/**
 * 配置代理 - 主动聊天
 */
export const proactiveConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/proactive/config')
      return response.data.config
    } else {
      const userConfig = await userConfigApi.getConfig()
      if (userConfig.proactive_chat && Object.keys(userConfig.proactive_chat).length > 0) {
        return userConfig.proactive_chat
      }
      const response = await api.get('/proactive/config')
      return response.data.config
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      await api.post('/proactive/config', config)
    } else {
      await userConfigApi.updateConfig({ proactive_chat: config })
    }
  },
}

/**
 * 配置代理 - 系统设置（LLM + 适配器 + 系统提示词）
 */
export const systemConfigProxy = {
  getConfig: async () => {
    if (isCurrentUserAdmin()) {
      const response = await api.get('/config')
      return response.data
    } else {
      // 普通用户获取合并后的配置（全局 + 用户覆盖）
      const [globalResp, userConfig] = await Promise.all([
        api.get('/config'),
        userConfigApi.getConfig(),
      ])
      const globalCfg = globalResp.data
      // 合并用户配置到全局配置上
      return {
        ...globalCfg,
        llm: userConfig.llm ? { ...globalCfg.llm, ...userConfig.llm } : globalCfg.llm,
        system_prompt: userConfig.system_prompt || globalCfg.system_prompt,
        tts: userConfig.tts ? { ...globalCfg.tts, ...userConfig.tts } : globalCfg.tts,
      }
    }
  },

  updateConfig: async (config: any) => {
    if (isCurrentUserAdmin()) {
      const response = await api.post('/config', config)
      return response.data
    } else {
      // 普通用户只保存 LLM 和系统提示词到用户配置
      const updateData: any = {}
      if (config.llm) updateData.llm = config.llm
      if (config.system_prompt !== undefined) updateData.system_prompt = config.system_prompt
      if (config.tts) updateData.tts = config.tts
      await userConfigApi.updateConfig(updateData)
    }
  },
}
