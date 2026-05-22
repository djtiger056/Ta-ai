import asyncio
import importlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


@dataclass
class MCPPluginSpec:
    """定义一个可安装的 MCP 插件"""

    name: str
    type: str = "python"  # builtin / python
    module: Optional[str] = None
    class_name: Optional[str] = None
    pip: Optional[str] = None
    description: str = ""
    auto_context: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


class MCPPlugin:
    """MCP 插件基础接口"""

    name: str = "plugin"
    description: str = ""
    auto_context: bool = False

    def list_tools(self) -> List[Dict[str, Any]]:
        """返回插件支持的工具列表"""
        return []

    async def run_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """运行指定工具"""
        raise NotImplementedError

    async def auto_context_block(self, user_message: str) -> Optional[str]:
        """当 auto_context 为 True 时，可提供自动上下文"""
        return None


class ClockPlugin(MCPPlugin):
    """内置时钟插件：提供当前时间，解决机器人没有时间观念的问题"""

    name = "clock"
    description = "提供当前本地/UTC 时间和日期的内置插件"
    auto_context = True

    def __init__(self):
        self._local_tz = self._resolve_timezone()

    def _resolve_timezone(self):
        """优先使用配置或环境指定的时区，回退到系统时区"""
        tz_preference = os.getenv("CLOCK_TIMEZONE")
        try:
            from backend.config import config

            tz_preference = tz_preference or config.get("clock", {}).get("timezone")
            if not tz_preference:
                # Fall back to proactive chat timezone if clock-specific setting is missing
                tz_preference = config.proactive_chat_config.get("timezone")
        except Exception:
            # 配置不可用时忽略，使用环境或系统默认
            pass

        tz = self._parse_timezone(tz_preference)
        if tz:
            return tz

        try:
            # 使用系统当前时区；在 Windows 上依赖操作系统时间设置
            return datetime.now().astimezone().tzinfo or timezone.utc
        except Exception:
            return timezone.utc

    def _parse_timezone(self, tz_name: Optional[str]):
        """解析 IANA 时区或 UTC±HH[:MM] 偏移字符串"""
        if not tz_name:
            return None

        tz_name = tz_name.strip()

        # 尝试 IANA 时区名称（如 Asia/Shanghai）
        if ZoneInfo:
            try:
                return ZoneInfo(tz_name)
            except Exception:
                pass

        # 解析 UTC 偏移（如 UTC+8、UTC+08:00）
        offset_match = re.match(r"UTC([+-])(\d{1,2})(?::?(\d{2}))?$", tz_name, re.IGNORECASE)
        if offset_match:
            sign = offset_match.group(1)
            hours = int(offset_match.group(2))
            minutes = int(offset_match.group(3) or 0)
            delta = timedelta(hours=hours, minutes=minutes)
            if sign == "-":
                delta = -delta
            return timezone(delta, name=f"UTC{sign}{hours:02d}:{minutes:02d}")

        return None

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "now",
                "description": "获取当前本地时间、UTC 时间和时间戳",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_timezone": {
                            "type": "boolean",
                            "description": "是否返回 ISO 字符串中的时区信息",
                        }
                    },
                    "required": [],
                },
            }
        ]

    async def run_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        if tool_name != "now":
            raise ValueError(f"ClockPlugin 不支持的工具: {tool_name}")

        now_local = datetime.now(self._local_tz)
        now_utc = datetime.now(timezone.utc)
        include_tz = bool(params.get("include_timezone", True))

        def fmt(dt: datetime) -> str:
            return dt.isoformat() if include_tz else dt.replace(tzinfo=None).isoformat()

        return {
            "local_time": fmt(now_local),
            "utc_time": fmt(now_utc),
            "timestamp": now_utc.timestamp(),
            "timezone": str(self._local_tz),
        }

    async def auto_context_block(self, user_message: str) -> Optional[str]:
        now_local = datetime.now(self._local_tz)
        now_utc = datetime.now(timezone.utc)
        tz_label = str(self._local_tz)
        return (
            f"当前本地时间（{tz_label}，24小时制，回答用户时请以此为准）: "
            f"{now_local.strftime('%Y-%m-%d %H:%M:%S')}，"
            f"UTC 时间: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}"
        )


class MCPManager:
    """负责 MCP 插件的安装、加载和执行"""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or Path("data") / "mcp_plugins.json"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._plugin_specs: Dict[str, MCPPluginSpec] = {}
        self._plugins: Dict[str, MCPPlugin] = {}

        self._load_registry()
        self._ensure_builtin_plugins()
        self._load_plugins()

    def _load_registry(self):
        """从磁盘加载插件配置"""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for name, spec_dict in data.items():
                        self._plugin_specs[name] = MCPPluginSpec(name=name, **spec_dict)
            except Exception as exc:
                print(f"[MCP] 读取插件配置失败，已重置: {exc}")
                self._plugin_specs = {}
        else:
            self._plugin_specs = {}
            self._save_registry()

    def _save_registry(self):
        """保存插件配置"""
        serializable = {
            name: {
                "type": spec.type,
                "module": spec.module,
                "class_name": spec.class_name,
                "pip": spec.pip,
                "description": spec.description,
                "auto_context": spec.auto_context,
                "meta": spec.meta,
            }
            for name, spec in self._plugin_specs.items()
        }
        self.registry_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")

    def _ensure_builtin_plugins(self):
        """确保内置/内置级别插件存在"""
        changed = False

        if "clock" not in self._plugin_specs:
            self._plugin_specs["clock"] = MCPPluginSpec(
                name="clock",
                type="builtin",
                module="backend.mcp.manager",
                class_name="ClockPlugin",
                description=ClockPlugin.description,
                auto_context=True,
            )
            changed = True

        if "daily_habits" not in self._plugin_specs:
            self._plugin_specs["daily_habits"] = MCPPluginSpec(
                name="daily_habits",
                type="python",
                module="backend.mcp.daily_habits",
                class_name="DailyHabitsPlugin",
                description="根据设定的作息表返回当前生活状态，为对话提供生活化上下文。",
                auto_context=True,
            )
            changed = True

        if "bing_cn_search" not in self._plugin_specs:
            self._plugin_specs["bing_cn_search"] = MCPPluginSpec(
                name="bing_cn_search",
                type="python",
                module="backend.mcp.bing_cn_search",
                class_name="BingCnSearchPlugin",
                description="使用必应中文搜索实时检索网络信息，并支持网页正文抓取。",
                auto_context=True,
            )
            changed = True

        if changed:
            self._save_registry()

    def _load_plugins(self):
        """根据配置加载所有插件"""
        self._plugins.clear()
        for name, spec in self._plugin_specs.items():
            plugin = self._create_plugin(name, spec)
            if plugin:
                self._plugins[name] = plugin

    def _create_plugin(self, name: str, spec: MCPPluginSpec) -> Optional[MCPPlugin]:
        try:
            if spec.type == "builtin":
                if name == "clock":
                    return ClockPlugin()
                return None

            if spec.type == "python":
                if not spec.module:
                    raise ValueError("缺少 module，无法加载 MCP 插件")
                module = importlib.import_module(spec.module)
                cls_name = spec.class_name or "Plugin"
                plugin_cls = getattr(module, cls_name)
                plugin = plugin_cls()  # type: ignore
                # 保底填充插件元数据
                if not getattr(plugin, "name", None):
                    plugin.name = name  # type: ignore
                if not getattr(plugin, "description", None):
                    plugin.description = spec.description  # type: ignore
                if getattr(plugin, "auto_context", None) is None:
                    plugin.auto_context = bool(spec.auto_context)  # type: ignore
                return plugin

            raise ValueError(f"未知的 MCP 插件类型: {spec.type}")
        except Exception as exc:
            print(f"[MCP] 加载插件 {name} 失败: {exc}")
            return None

    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出已加载的插件及工具"""
        result: List[Dict[str, Any]] = []
        for name, plugin in self._plugins.items():
            try:
                tools = plugin.list_tools()
            except Exception as exc:
                print(f"[MCP] 读取插件 {name} 工具失败: {exc}")
                tools = []
            result.append(
                {
                    "name": name,
                    "description": getattr(plugin, "description", ""),
                    "auto_context": bool(getattr(plugin, "auto_context", False)),
                    "tools": tools,
                }
            )
        return result

    async def execute_tool(
        self, plugin_name: str, tool_name: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """执行指定插件的工具"""
        if plugin_name not in self._plugins:
            raise ValueError(f"未找到 MCP 插件: {plugin_name}")
        plugin = self._plugins[plugin_name]

        runner = plugin.run_tool
        if asyncio.iscoroutinefunction(runner):
            return await runner(tool_name, params or {})
        return await asyncio.to_thread(runner, tool_name, params or {})

    async def collect_auto_context(self, user_message: str) -> List[str]:
        """收集需要自动注入的上下文"""
        blocks: List[str] = []
        for name, plugin in self._plugins.items():
            if not getattr(plugin, "auto_context", False):
                continue
            try:
                context_fn = plugin.auto_context_block
                if asyncio.iscoroutinefunction(context_fn):
                    block = await context_fn(user_message)
                else:
                    block = await asyncio.to_thread(context_fn, user_message)
                if block:
                    blocks.append(f"[{name}] {block}")
            except Exception as exc:
                print(f"[MCP] 收集插件 {name} 自动上下文失败: {exc}")
        return blocks

    def install_plugin(
        self,
        name: str,
        pip_spec: str,
        module: str,
        class_name: str = "Plugin",
        description: str = "",
        auto_context: bool = False,
        meta: Optional[Dict[str, Any]] = None,
    ) -> MCPPluginSpec:
        """通过 pip 安装并注册 MCP 插件"""
        if name in self._plugin_specs:
            raise ValueError(f"插件 {name} 已存在")

        print(f"[MCP] 开始安装插件 {name}，pip: {pip_spec}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_spec],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pip 安装失败: {result.stderr.strip()}")

        spec = MCPPluginSpec(
            name=name,
            type="python",
            module=module,
            class_name=class_name,
            pip=pip_spec,
            description=description,
            auto_context=auto_context,
            meta=meta or {},
        )
        self._plugin_specs[name] = spec
        self._save_registry()
        plugin = self._create_plugin(name, spec)
        if plugin:
            self._plugins[name] = plugin
        return spec


__all__ = ["MCPManager", "MCPPlugin", "ClockPlugin", "MCPPluginSpec"]
