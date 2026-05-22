export interface LLMConfig {
  provider: string
  model: string
  api_base: string
  api_key: string
  temperature: number
  max_tokens: number
}

export interface AdapterConfig {
  console: {
    enabled: boolean
  }
  qq: {
    enabled: boolean
    ws_host: string
    ws_port: number
    access_token: string
    need_at: boolean
  }
}

export interface SystemConfig {
  llm: LLMConfig
  adapters: AdapterConfig
  system_prompt: string
  tts?: TTSConfig
  asr?: ASRConfig
  video_generation?: Record<string, any>
}

export interface TTSConfig {
  enabled: boolean
  probability: number
  voice_only_when_tts: boolean
  provider: string
  qihang: {
    api_base: string
    api_key: string
    model: string
    voice: string
  }
  qwen: {
    api_key: string
    model: string
    voice_id: string
    preferred_name: string
    customization_url: string
    realtime_ws_url: string
    voice_sample_file: string
    audio_format: string
    synthesis_type: number
    volume: number
    speech_rate: number
    pitch_rate: number
    seed: number
    instruction?: string
    language_hints?: string[]
    timeout_millis: number
  }
  segment_config: {
    enabled: boolean
    strategy: string
    max_segments: number
    send_timing: string
    delay_range: [number, number]
    min_segment_length: number
    max_segment_length: number
    interval_step: number
  }
  randomization: {
    enabled: boolean
    full_probability: number
    partial_probability: number
    none_probability: number
    min_partial_sentences: number
    max_partial_sentences: number
  }
  text_cleaning: {
    enabled: boolean
    remove_emoji: boolean
    remove_kaomoji: boolean
    remove_action_text: boolean
    remove_brackets_content: boolean
    remove_markdown: boolean
    max_length: number
  }
}

export interface VoiceCharacter {
  name: string
  description: string
}

export interface ASRConfig {
  enabled: boolean
  provider: string
  auto_send_to_llm: boolean
  processing_message: string
  error_message: string
  siliconflow: {
    api_base: string
    api_key: string
    model: string
    timeout: number
  }
  qwen: {
    api_base: string
    api_key: string
    model: string
    timeout: number
  }
  assemblyai: {
    api_base: string
    api_key: string
    model: string
    timeout: number
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  emote?: EmotePayload
}

export interface EmotePayload {
  category: string
  file_name: string
  file_path: string
  mime_type: string
  matched_keywords?: string[]
  data_url: string
}

export interface Personality {
  name: string
  description: string
  system_prompt: string
  traits: string[]
}

export interface WordBankItem {
  text: string
  enabled: boolean
  weight: number
}

export interface WordBankCategory {
  path: string
  name: string
  enabled: boolean
  pick_count: number
  items: WordBankItem[]
  is_builtin: boolean
}

export interface PresetConfig {
  name: string
  description: string
  outfit_style: string
  scene_type: string
  enabled: boolean
  categories?: string[]
  pick_count_overrides?: Record<string, number>
}

export interface IntentRule {
  name: string
  description?: string
  enabled?: boolean
  keywords: string[]
  categories: string[]
  pick_count_overrides?: Record<string, number>
}

export interface PromptEnhancerConfig {
  enabled: boolean
  mode?: string
  categories: Record<string, boolean>
  pick_count?: Record<string, number>
  presets: PresetConfig[]
  current_preset: string
  builtin_word_bank_path?: string
  custom_word_bank_path?: string
  allow_edit_builtin?: boolean
  intents?: IntentRule[]
}

export interface PromptEnhancePreview {
  original: string
  enhanced: string
  intents: Record<string, boolean>
  is_enhanced: boolean
}

export interface EmoteCategory {
  name: string
  keywords: string[]
  weight: number
  enabled: boolean
  path?: string
  description?: string
}

export interface EmoteConfig {
  enabled: boolean
  send_probability: number
  base_path: string
  max_per_message: number
  file_extensions?: string[]
  categories: EmoteCategory[]
}

export interface EmoteCategoryInfo extends EmoteCategory {
  file_count: number
  sample_files: string[]
  path: string
}

export interface EmoteConfigResponse {
  config: EmoteConfig
  categories: EmoteCategoryInfo[]
  base_path: string
}

export interface CerebellumState {
  intensities: Record<string, number>
  baselines: Record<string, number>
  dominant_emotion: string
  dominant_emotion_label?: string
  last_updated_at: string
  last_tick_duration_ms: number
  last_triggered_emotion?: string | null
  last_triggered_emotion_label?: string | null
}

export interface CerebellumMotivation {
  motivation_type: string
  motivation_label: string
  intensity: number
  description: string
  suggested_action: string
  dominant_emotion: string
  dominant_emotion_label: string
  dominant_emotion_intensity: number
  status: string
  created_at?: string | null
  target_key?: string | null
}

export interface CerebellumHistoryItem {
  timestamp: string
  intensities: Record<string, number>
  dominant_emotion: string
  motivation_types: string[]
}

// ---- 每日作息生成 ----

export interface GeneratedScheduleSlot {
  start: string
  end: string
  activity: string
  desc: string
}

export interface GeneratedScheduleStatus {
  generated: boolean
  date: string | null
  generated_at: string | null
  slot_count: number
  config_enabled: boolean
}

export interface GeneratedScheduleData {
  date: string
  generated_at: string
  slots: GeneratedScheduleSlot[]
}

export interface DailyScheduleGenConfig {
  enabled: boolean
  generate_window_start: string
  generate_window_end: string
  persona_name: string
  persona_desc: string
  prompt_template: string
  timezone?: string
  llm?: {
    provider?: string
    api_base?: string
    api_key?: string
    model?: string
    temperature?: number
    max_tokens?: number
  } | null
}
