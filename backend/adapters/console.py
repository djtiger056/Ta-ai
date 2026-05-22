import asyncio
from typing import Optional
from ..core.bot import Bot


class ConsoleAdapter:
    """控制台适配器，提供命令行交互界面"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
    
    async def start(self):
        """启动控制台交互"""
        self.running = True
        print("=" * 50)
        print("🤖 LFBot 控制台模式")
        print("输入 'help' 查看帮助")
        print("输入 'quit' 或 'exit' 退出")
        print("输入 'clear' 清空对话历史")
        print("输入 'history' 查看对话历史")
        print("输入 'test' 测试API连接")
        print("=" * 50)
        
        # 测试连接
        print("正在测试API连接...")
        if await self.bot.test_connection():
            print("✅ API连接成功！")
        else:
            print("❌ API连接失败，请检查配置")
        
        print()
        
        while self.running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "你: "
                )
                
                if not user_input.strip():
                    continue
                
                await self.handle_input(user_input.strip())
                
            except KeyboardInterrupt:
                print("\n👋 输入已中断，控制台退出")
                break
            except EOFError:
                print("\n👋 输入流结束，控制台退出")
                break
            except Exception as e:
                print(f"❌ 发生错误: {str(e)}")
    
    async def handle_input(self, user_input: str):
        """处理用户输入"""
        if user_input.lower() in ['quit', 'exit', '退出']:
            self.running = False
            print("👋 控制台已退出")
            return
        
        if user_input.lower() in ['help', '帮助']:
            self.show_help()
            return
        
        if user_input.lower() in ['clear', '清空']:
            self.bot.clear_history()
            print("🧹 对话历史已清空")
            return
        
        if user_input.lower() in ['history', '历史']:
            self.show_history()
            return
        
        if user_input.lower() in ['test', '测试']:
            print("正在测试API连接...")
            if await self.bot.test_connection():
                print("✅ API连接成功！")
            else:
                print("❌ API连接失败，请检查配置")
            return
        
        # 普通对话
        print("🤖: ", end="", flush=True)
        try:
            async for chunk in self.bot.chat_stream(user_input):
                print(chunk, end="", flush=True)
            print()  # 换行
        except Exception as e:
            print(f"\n❌ 回复失败: {str(e)}")
    
    def show_help(self):
        """显示帮助信息"""
        print("\n📖 帮助信息:")
        print("  help/帮助    - 显示此帮助信息")
        print("  quit/exit/退出 - 退出程序")
        print("  clear/清空   - 清空对话历史")
        print("  history/历史 - 查看对话历史")
        print("  test/测试    - 测试API连接")
        print()
    
    def show_history(self):
        """显示对话历史"""
        history = self.bot.get_history()
        if not history:
            print("📝 暂无对话历史")
            return
        
        print("\n📝 对话历史:")
        print("-" * 50)
        for i, msg in enumerate(history):
            role = "系统" if msg["role"] == "system" else ("你" if msg["role"] == "user" else "🤖")
            print(f"{role}: {msg['content']}")
            if i < len(history) - 1:
                print()
        print("-" * 50)
        print()
