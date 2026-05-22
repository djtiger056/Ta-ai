import shutil
import yaml
from typing import Dict, Any
from pathlib import Path


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # 如果是相对路径，则相对于项目根目录
        if not Path(config_path).is_absolute():
            project_root = Path(__file__).parent.parent
            self.config_path = project_root / config_path
        else:
            self.config_path = Path(config_path)
        self.example_config_path = self.config_path.with_name("config.example.yaml")
        self._ensure_config_file()
        self._config = self._load_config()

    def _ensure_config_file(self) -> None:
        """确保运行时配置文件存在。

        如果仓库里只有 `config.example.yaml`，首次启动时自动复制一份
        到 `config.yaml`，这样克隆后可以直接启动而不必手动拷贝。
        """
        if self.config_path.exists():
            return

        if self.example_config_path.exists():
            shutil.copyfile(self.example_config_path, self.config_path)
            return

        raise FileNotFoundError(
            f"配置文件未找到: {self.config_path}，且缺少示例文件: {self.example_config_path}"
        )
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件未找到: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")
    
    @property
    def llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self._config.get('llm', {})
    
    @property
    def system_prompt(self) -> str:
        """获取系统提示词（人设层）"""
        return self._config.get('system_prompt', '')

    @property
    def system_rules(self) -> str:
        """获取功能协议层提示词（视觉/语音/委派等协议，与人设分离）"""
        return self._config.get('system_rules', '')
    
    @property
    def adapters_config(self) -> Dict[str, Any]:
        """获取适配器配置"""
        return self._config.get('adapters', {})
    
    @property
    def server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self._config.get('server', {})
    
    @property
    def tts_config(self) -> Dict[str, Any]:
        """获取TTS配置"""
        return self._config.get('tts', {})

    @property
    def voice_gateway_config(self):
        """获取语音网关配置"""
        from backend.voice_gateway.config import VoiceGatewayConfig
        gateway_dict = self._config.get('voice_gateway', {})
        return VoiceGatewayConfig.from_dict(gateway_dict)
    
    @property
    def image_gen_config(self):
        """获取图像生成配置"""
        from backend.image_gen.config import ImageGenerationConfig
        image_gen_dict = self._config.get('image_generation', {})
        return ImageGenerationConfig(**image_gen_dict)
    
    @property
    def vision_config(self):
        """获取视觉识别配置"""
        from backend.vision.config import VisionRecognitionConfig
        vision_dict = self._config.get('vision', {})
        return VisionRecognitionConfig(**vision_dict)

    @property
    def prompt_enhancer_config(self):
        """获取提示词增强配置"""
        from backend.prompt_enhancer.config import PromptEnhancerConfig
        enhancer_dict = self._config.get('prompt_enhancer', {})
        return PromptEnhancerConfig(**enhancer_dict)

    @property
    def asr_config(self):
        """获取ASR语音识别配置"""
        from backend.asr.config import ASRConfig
        asr_dict = self._config.get('asr', {})
        return ASRConfig(**asr_dict)

    @property
    def emote_config(self):
        """获取表情包发送配置"""
        from backend.emote.models import EmoteConfig
        emote_dict = self._config.get('emotes', {})
        return EmoteConfig(**emote_dict)

    @property
    def memory_config(self):
        """获取记忆系统配置"""
        from backend.memory.models import MemoryConfig
        # 兼容历史配置：早期版本可能把记忆配置放在 llm.memory 下
        legacy_memory_dict = self._config.get('llm', {}).get('memory', {})
        memory_dict = self._config.get('memory', {})

        merged_memory_dict: Dict[str, Any] = {}
        if isinstance(legacy_memory_dict, dict):
            self._deep_update(merged_memory_dict, legacy_memory_dict)
        if isinstance(memory_dict, dict):
            # 顶层 memory 优先级更高
            self._deep_update(merged_memory_dict, memory_dict)

        memory_dict = merged_memory_dict
        return MemoryConfig(**memory_dict)

    @property
    def agent_delegate_config(self):
        """获取 Agent 委派配置"""
        from backend.agent_delegate.config import AgentDelegateConfig
        delegate_dict = self._config.get('agent_delegate', {})
        return AgentDelegateConfig.from_dict(delegate_dict)

    @property
    def clock_config(self) -> Dict[str, Any]:
        """获取时钟插件相关配置"""
        return self._config.get('clock', {})
    
    @property
    def proactive_chat_config(self) -> Dict[str, Any]:
        """获取主动聊天配置"""
        cerebellum_cfg = self._config.get('cerebellum', {})
        if isinstance(cerebellum_cfg, dict):
            proactive_cfg = cerebellum_cfg.get('proactive_chat')
            if isinstance(proactive_cfg, dict):
                return proactive_cfg
        return self._config.get('proactive_chat', {})

    @property
    def qq_access_control_config(self) -> Dict[str, Any]:
        """获取 QQ 访问控制配置"""
        qq_config = self._config.get('adapters', {}).get('qq', {})
        return qq_config.get('access_control', {
            'enabled': False,
            'mode': 'disabled',
            'whitelist': [],
            'blacklist': [],
            'deny_message': '抱歉，你没有权限使用此机器人。'
        })

    def get(self, key: str, default=None):
        """获取配置项"""
        return self._config.get(key, default)
    
    def _deep_update(self, target: Dict[str, Any], source: Dict[str, Any]):
        """深度合并字典，递归处理嵌套字典
        
        Args:
            target: 目标字典（将被更新）
            source: 源字典（提供更新值）
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # 递归合并嵌套字典
                self._deep_update(target[key], value)
            else:
                # 直接更新值（或覆盖整个字典）
                target[key] = value
    
    def update_config(self, section: str, config_dict: Dict[str, Any]):
        """更新配置并保存到文件
        
        Args:
            section: 配置节名称，如 'image_generation'
            config_dict: 要更新的配置字典
        """
        # 更新内存中的配置
        if section not in self._config:
            self._config[section] = {}
        
        # 深度合并配置
        self._deep_update(self._config[section], config_dict)
        
        # 保存到文件
        self._save_config()

    def refresh_from_file(self):
        """重新从配置文件载入，便于热更新"""
        self._config = self._load_config()
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            raise Exception(f"配置文件保存失败: {e}")


# 全局配置实例
config = Config()
