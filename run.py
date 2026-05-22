#!/usr/bin/env python3
"""
LFBot 启动脚本
支持虚拟环境检测和引导
"""

import sys
import os
from pathlib import Path


def ensure_utf8_output() -> None:
    """
    Make sure stdout/stderr use UTF-8 so emoji and CJK characters don't break
    when the console default is GBK.
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # If reconfigure is not supported we silently continue.
            pass


ensure_utf8_output()


def is_venv_active() -> bool:
    """检查当前是否在虚拟环境中运行"""
    # 两种常见的虚拟环境检测方法
    # 1. virtualenv创建的环境有real_prefix属性
    # 2. venv创建的环境有base_prefix != prefix
    return (hasattr(sys, 'real_prefix') or 
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))


def check_virtual_environment(project_root: Path) -> None:
    """
    检查虚拟环境状态并提供相应指引
    """
    if is_venv_active():
        print("✅ 虚拟环境已激活")
        return
    
    # 未在虚拟环境中运行
    print("\n" + "="*60)
    print("⚠️  虚拟环境警告")
    print("="*60)
    
    venv_path = project_root / "venv"
    
    if venv_path.exists():
        print("检测到虚拟环境目录，但未激活虚拟环境。")
        print("\n📋 请先激活虚拟环境：")
        print(f"    {venv_path}\\Scripts\\activate")
        print("\n或者运行 setup.bat 自动激活：")
        print("    setup.bat")
    else:
        print("未检测到虚拟环境。建议使用虚拟环境运行本项目。")
        print("\n📋 请设置虚拟环境：")
        print("    1. 运行 setup.bat 自动设置")
        print("    2. 或手动创建：python -m venv venv")
        print("    3. 然后激活：venv\\Scripts\\activate")
        print("    4. 安装依赖：pip install -r requirements.txt")
    
    print("\n🔍 当前Python环境：")
    print(f"    Python路径: {sys.executable}")
    print(f"    Python版本: {sys.version.split()[0]}")
    
    print("\n⚠️  风险提示：")
    print("    在系统环境中运行可能导致：")
    print("    - 依赖冲突（与其他项目）")
    print("    - 版本不一致问题")
    print("    - 环境难以复现")
    
    print("\n⏳ 3秒后继续运行（按Ctrl+C取消）...")
    try:
        import time
        for i in range(3, 0, -1):
            print(f"    {i}...", end='\r')
            time.sleep(1)
        print("    启动中...")
    except KeyboardInterrupt:
        print("\n❌ 启动已取消。")
        sys.exit(0)
    
    print("="*60 + "\n")


def check_and_free_port(port: int = 8003) -> None:
    """检查并释放指定端口"""
    import socket
    import subprocess
    
    try:
        # 检查端口是否被占用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', port))
            if result == 0:
                print(f"⚠️  端口 {port} 被占用，正在清理...")
                
                # 查找并停止占用端口的进程
                try:
                    if sys.platform == "win32":
                        # Windows系统
                        result = subprocess.run(
                            ['netstat', '-ano'], 
                            capture_output=True, 
                            text=True, 
                            shell=True
                        )
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if f':{port}' in line and 'LISTENING' in line:
                                parts = line.split()
                                if len(parts) >= 5:
                                    pid = parts[-1]
                                    try:
                                        subprocess.run(['taskkill', '/PID', pid, '/F'], 
                                                     capture_output=True, shell=True)
                                        print(f"   已停止进程 PID: {pid}")
                                    except:
                                        pass
                    else:
                        # Linux/Mac系统
                        subprocess.run(['fuser', '-k', f'{port}/tcp'], 
                                     capture_output=True, shell=True)
                    
                    print(f"✅ 端口 {port} 清理完成")
                    import time
                    time.sleep(2)  # 等待端口释放
                    
                except Exception as e:
                    print(f"   清理端口时出错: {e}")
            else:
                print(f"✅ 端口 {port} 可用")
    except Exception as e:
        print(f"   检查端口时出错: {e}")


def main() -> None:
    """主函数"""
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    print("🚀 启动 LFBot...")
    
    # 检查虚拟环境状态
    check_virtual_environment(project_root)
    
    # 如果虚拟环境未激活，尝试激活
    if not is_venv_active():
        print("⚠️  尝试自动激活虚拟环境...")
        venv_python = project_root / "venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            print(f"✅ 找到虚拟环境Python: {venv_python}")
            # 使用虚拟环境的Python重新运行此脚本
            import subprocess
            try:
                result = subprocess.run(
                    [str(venv_python), __file__] + sys.argv[1:],
                    cwd=str(project_root),
                    check=False
                )
                sys.exit(result.returncode)
            except Exception as e:
                print(f"❌ 自动激活失败: {e}")
                print("请手动运行以下命令激活虚拟环境:")
                print(f"   {project_root}\\venv\\Scripts\\activate")
                print("   python run.py")
                sys.exit(1)
        else:
            print("❌ 未找到虚拟环境，请先运行 setup.bat 创建虚拟环境")
            sys.exit(1)
    
    # 检查并清理端口
    check_and_free_port(8003)
    
    print("执行 backend.main...")
    import subprocess
    
    # 使用subprocess运行main.py，确保__name__ == "__main__"被执行
    try:
        result = subprocess.run(
            [sys.executable, "backend/main.py"],
            cwd=str(project_root),
            check=False
        )
        
        if result.returncode != 0:
            print(f"\n❌ 后端进程退出，返回码: {result.returncode}")
            sys.exit(result.returncode)
            
    except KeyboardInterrupt:
        print("\n👋 用户中断，正在关闭...")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)
        sys.exit(1)


if __name__ == "__main__":
    main()
