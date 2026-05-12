import asyncio
import sys
import uvicorn
from pathlib import Path
from typing import Optional

# Use selector loop on Windows to avoid Proactor connection reset noise.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.core.bot import Bot
from backend.adapters.console import ConsoleAdapter
from backend.adapters.qq import QQAdapter
from backend.adapters.linyu import LinyuAdapter
from backend.config import config
from backend.api.config import router as config_router
from backend.api.chat import router as chat_router
from backend.api.tts import router as tts_router
from backend.api.asr import router as asr_router
from backend.api.image_gen import router as image_gen_router
from backend.api.memory import router as memory_router
from backend.api.vision import router as vision_router
from backend.api.prompt_enhancer import router as prompt_enhancer_router
from backend.api.mcp import router as mcp_router
from backend.api import proactive as proactive_api
from backend.core.proactive import ProactiveChatScheduler
from backend.api import cerebellum as cerebellum_api
from backend.core.cerebellum import CerebellumEngine
from backend.api.emotes import router as emotes_router
from backend.api import reminder as reminder_api
from backend.api.access_control import router as access_control_router
from backend.memory.reminder_scheduler import ReminderScheduler
from backend.api.user_auth import router as user_auth_router
from backend.api.user_config import router as user_config_router
from backend.api.admin_users import router as admin_users_router
from backend.api.voice_session import router as voice_session_router
from backend.api.daily_schedule import router as daily_schedule_router
from backend.user import user_manager

# 创建 FastAPI 应用
app = FastAPI(title="LFBot API", version="1.0.0")

# 添加 CORS 中间件
# - 开发模式下允许 localhost/127.0.0.1 任意端口，避免 Vite 端口变化导致预检(OPTIONS) 400
# - 生产环境建议在 config.yaml 中显式配置 allow_origins/allow_origin_regex
cors_cfg = config.get("cors", {}) or {}
allow_origins = cors_cfg.get("allow_origins") or cors_cfg.get("origins") or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
allow_origin_regex = cors_cfg.get("allow_origin_regex")
if not allow_origin_regex and (config.server_config.get("debug", False) is True):
    allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if not allow_origin_regex else [],
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(config_router)
app.include_router(chat_router)
app.include_router(tts_router)
app.include_router(asr_router)
app.include_router(image_gen_router)
app.include_router(memory_router)
app.include_router(vision_router)
app.include_router(mcp_router)
app.include_router(prompt_enhancer_router)
app.include_router(proactive_api.router)
app.include_router(cerebellum_api.router)
app.include_router(emotes_router)
app.include_router(reminder_api.router)
app.include_router(access_control_router)
app.include_router(user_auth_router)
app.include_router(user_config_router)
app.include_router(admin_users_router)
app.include_router(voice_session_router)
app.include_router(daily_schedule_router)


@app.get("/api/health")
async def health():
    """健康检查接口"""
    return {"status": "ok", "message": "LFBot API Server"}


@app.get("/")
async def root(request: Request):
    """根路径：浏览器访问返回前端页面，其他返回 API 信息"""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and _frontend_dist.is_dir():
        return FileResponse(str(_frontend_dist / "index.html"))
    return {"message": "LFBot API Server"}


# ---- 前端静态文件服务 ----
_frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """SPA catch-all：非 /api 路径一律返回 index.html"""
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_frontend_dist / "index.html"))


async def start_adapters():
    """启动适配器与主动聊天调度器"""
    try:
        # 初始化用户数据库
        await user_manager.init_db()
        print("✓ 用户数据库已初始化")

        bot = Bot()

        # 通过统一的 bot_provider 设置全局 Bot 实例
        from backend.api.bot_provider import set_bot
        set_bot(bot)

        # 兼容 asr 模块仍需直接引用 bot_instance 的场景
        import backend.api.asr
        backend.api.asr.bot_instance = bot

        print("✓ 全局 Bot 实例已设置到所有 API 模块")

        # 初始化主动聊天调度器
        proactive_scheduler: Optional[ProactiveChatScheduler] = ProactiveChatScheduler(bot)
        cerebellum_engine: Optional[CerebellumEngine] = CerebellumEngine(
            proactive_dispatcher=proactive_scheduler.handle_motivation_signal if proactive_scheduler else None
        )
        cerebellum_api.set_engine(cerebellum_engine)

        # 初始化待办事项调度器
        reminder_scheduler: Optional[ReminderScheduler] = None
        reminder_cfg = config.get("reminder", {})
        if reminder_cfg.get("enabled", True):
            reminder_scheduler = ReminderScheduler(
                check_interval_seconds=reminder_cfg.get("check_interval", 60)
            )

            # 设置提醒回调函数
            async def send_reminder_callback(reminder_data: dict):
                """发送待办事项提醒"""
                user_id = reminder_data.get("user_id")
                session_id = reminder_data.get("session_id")
                content = reminder_data.get("content")
                trigger_time = reminder_data.get("trigger_time")
                reminder_message = reminder_data.get("reminder_message") or f"⏰ 提醒: {content}"

                # 根据会话类型发送提醒
                if session_id and session_id.startswith("qq_group_"):
                    # QQ群消息
                    if qq_adapter:
                        group_id = session_id.replace("qq_group_", "")
                        await qq_adapter.send_group_message(group_id, reminder_message)
                elif session_id and session_id.startswith("qq_private_"):
                    # QQ私聊
                    if qq_adapter:
                        user_qq_id = session_id.replace("qq_private_", "")
                        await qq_adapter.send_private_message(user_qq_id, reminder_message)
                else:
                    # 控制台输出
                    print(f"🔔 待办事项提醒 [{user_id}]: {reminder_message}")

            reminder_scheduler.set_reminder_callback(send_reminder_callback)
            reminder_api.scheduler_instance = reminder_scheduler
            print("⏰ 待办事项调度器已初始化")

        adapters_config = config.adapters_config
        tasks: list[asyncio.Task] = []

        if proactive_scheduler:
            async def _send_web_message(target: dict, payload):
                await proactive_scheduler.enqueue_web_message(target, payload)

            proactive_scheduler.register_sender("web", _send_web_message)

        # 控制台适配器
        console_adapter: Optional[ConsoleAdapter] = None
        console_config = adapters_config.get("console", {})
        if console_config.get("enabled", False):
            console_adapter = ConsoleAdapter(bot)
            print("🖥️ 控制台适配器已启用")

        # QQ 适配器
        qq_adapter: Optional[QQAdapter] = None
        qq_config = adapters_config.get("qq", {})
        if qq_config.get("enabled", False):
            qq_adapter = QQAdapter(bot)
            print("💬 QQ 适配器已启用")

            if proactive_scheduler:
                async def _send_qq_private(target: dict, payload):
                    user = target.get("user_id")
                    if not user:
                        return
                    if isinstance(payload, dict):
                        text = payload.get("text")
                        image = payload.get("image")
                        if text:
                            await qq_adapter.send_private_message(user, text)
                        if image:
                            await qq_adapter.send_image_message(user, image)
                    else:
                        await qq_adapter.send_private_message(user, str(payload))

                async def _send_qq_group(target: dict, payload):
                    group = target.get("user_id")
                    if not group:
                        return
                    if isinstance(payload, dict):
                        text = payload.get("text")
                        image = payload.get("image")
                        if text:
                            await qq_adapter.send_group_message(group, text)
                        if image:
                            await qq_adapter.send_image_message(group, image, is_group=True, group_id=group)
                    else:
                        await qq_adapter.send_group_message(group, str(payload))

                proactive_scheduler.register_sender("qq_private", _send_qq_private)
                proactive_scheduler.register_sender("qq_group", _send_qq_group)

        # Linyu 适配器
        linyu_adapter: Optional[LinyuAdapter] = None
        linyu_config = adapters_config.get("linyu", {})
        if linyu_config.get("enabled", False):
            linyu_adapter = LinyuAdapter(bot)
            print("💬 Linyu 适配器已启用")

            if proactive_scheduler:
                async def _send_linyu_private(target: dict, payload):
                    user = target.get("user_id")
                    if not user:
                        return
                    if isinstance(payload, dict):
                        text = payload.get("text")
                        image = payload.get("image")
                        if text:
                            await linyu_adapter.send_private_message(user, text)
                        if image:
                            await linyu_adapter.send_image_message(user, image)
                    else:
                        await linyu_adapter.send_private_message(user, str(payload))

                proactive_scheduler.register_sender("linyu_private", _send_linyu_private)

        # 启动主动聊天调度器后再启动各适配器，避免被长运行任务阻塞
        if proactive_scheduler:
            await proactive_scheduler.start()
            proactive_api.scheduler_instance = proactive_scheduler
            print("🤖 主动聊天调度器已启动")
            if proactive_scheduler.task:
                tasks.append(proactive_scheduler.task)

        if cerebellum_engine:
            await cerebellum_engine.start()
            print("🧠 小脑情感引擎已启动")
            if cerebellum_engine.task:
                tasks.append(cerebellum_engine.task)

        # 启动待办事项调度器
        if reminder_scheduler:
            await reminder_scheduler.start()
            print("⏰ 待办事项调度器已启动")
            if reminder_scheduler.task:
                tasks.append(reminder_scheduler.task)

        if qq_adapter:
            tasks.append(asyncio.create_task(qq_adapter.start()))
        if linyu_adapter:
            tasks.append(asyncio.create_task(linyu_adapter.start()))
        if console_adapter:
            tasks.append(asyncio.create_task(console_adapter.start()))

        if tasks:
            await asyncio.gather(*tasks)
        else:
            print("⚠️ 没有启用任何适配器，也未启动主动聊天调度器")

    except KeyboardInterrupt:
        print("\n👋 适配器已停止")
    except Exception as e:
        print(f"❌ 适配器启动失败: {str(e)}")


if __name__ == "__main__":
    import threading

    print("Starting adapters in background thread...")
    # 在后台线程启动适配器
    adapter_thread = threading.Thread(target=lambda: asyncio.run(start_adapters()))
    adapter_thread.daemon = True
    adapter_thread.start()

    print("Starting FastAPI server...")
    # 启动 FastAPI 服务器
    server_config = config.server_config
    print(f"Server config: {server_config}")
    log_level = str(server_config.get("log_level", "info")).lower()
    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8000),
        log_level=log_level,
    )
