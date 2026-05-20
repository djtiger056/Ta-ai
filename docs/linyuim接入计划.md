Linyu IM 接入实施计划
一、项目概述
目标： 将自建的 linyu IM 通讯平台接入到当前 AI 伴侣项目中

核心优势（相比 QQ 接入）：

无需中间层工具（如 napcat），直接调用 linyu API
可完全控制消息格式和交互逻辑
"AI伴侣"模式：用户与 AI 伴侣账号互为好友，提升亲密感
部署模式： 单用户模式

1 个用户账号（你自己使用）
1 个 AI 伴侣账号（Bot 登录使用）
两者互为好友，通过私聊交流
二、技术方案
2.1 接入方式：WebSocket 直连
选择理由：

实时性最好（消息推送，无延迟）
类似当前 QQ 适配器架构，迁移成本低
linyu 已提供 WebSocket 服务（端口 9100）
通信流程：


1. HTTP API 登录 → 获取 JWT Token
2. WebSocket 连接 → 实时接收消息
3. HTTP API 发送 → 回复消息
2.2 linyu 关键 API
功能	端点	说明
登录	POST /v1/api/login	获取 JWT Token
发送消息	POST /v1/api/message/send	发送文本消息
发送图片	POST /v1/api/message/send/Img	发送图片
发送文件	POST /v1/api/message/send/file	发送语音/文件
好友列表	GET /v1/api/friend/list	获取好友
消息已读	GET /v1/api/chat-list/read/{targetId}	标记已读
WebSocket 服务： ws://host:9100（需研究具体协议格式）

三、实现步骤
阶段 1：基础连接
新建文件： backend/adapters/linyu.py

核心类结构：


class LinyuAdapter:
    def __init__(self, bot: Bot)
    async def start()                    # 启动适配器
    async def stop()                     # 停止适配器
    async def _authenticate()            # HTTP 登录获取 Token
    async def _connect_websocket()       # 建立 WebSocket 连接
    async def _handle_messages()         # 消息接收循环
验收标准： 能够登录并接收到 linyu 的消息推送

阶段 2：消息处理
核心方法：


async def _handle_private_message(data)  # 处理私聊消息
async def send_private_message(user_id, message)  # 发送文本
def _parse_message_content(msg_content)  # 解析消息内容
与 Bot 集成：


# 接收消息 → 调用 Bot.chat() → 发送回复
response = await self.bot.chat(text_content, user_id=from_id, session_id=from_id)
await self.send_private_message(from_id, response)
验收标准： 能够接收用户消息并回复文本

阶段 3：多模态支持
图片消息：

接收图片 → bot.recognize_image() → 图像识别
图像生成 → bot.generate_image() → 发送图片
语音消息：

接收语音 → bot.transcribe_voice() → 语音识别
语音合成 → bot.synthesize_speech() → 发送语音
验收标准： 支持图片和语音交互

阶段 4：稳定性优化
自动重连机制
心跳检测
消息分段发送
错误处理和日志
验收标准： 24 小时稳定运行

四、配置文件设计
在 config.yaml 中添加：


adapters:
  linyu:
    enabled: true
    
    # 连接配置
    http_host: your-linyu-server.com  # linyu 服务器地址
    http_port: 9200                    # HTTP API 端口
    ws_host: your-linyu-server.com
    ws_port: 9100                      # WebSocket 端口
    
    # AI 伴侣账号（机器人登录用，手动在 linyu 中注册）
    account: "ai_companion"
    password: "your_password"
    
    # 聊天对象（你的 linyu 用户 ID）
    target_user_id: "your_user_id"
    
    # 访问控制（单用户模式）
    access_control:
      enabled: true
      mode: whitelist
      whitelist:
        - "your_user_id"
      deny_message: "抱歉，我只能和主人聊天哦~"
    
    # 分段发送
    segment_config:
      enabled: true
      max_segment_length: 100
      delay_range: [1.0, 3.0]
      strategy: sentence
    
    # 重连配置
    reconnect_config:
      max_attempts: 10
      interval: 5.0
      heartbeat_interval: 30.0
五、关键文件清单
文件	操作	说明
backend/adapters/linyu.py	新建	LinyuAdapter 核心实现
backend/adapters/__init__.py	修改	导出 LinyuAdapter
backend/main.py	修改	注册 linyu 适配器启动
config.yaml	修改	添加 linyu 配置项
参考文件：

backend/adapters/qq.py - 复用 WebSocket 连接、重连、分段发送逻辑
backend/core/bot.py - Bot 核心接口
六、待研究事项
6.1 linyu WebSocket 协议
需要确认的内容：

连接方式： Token 如何传递？查询参数还是消息体？
消息格式： WebSocket 推送的 JSON 结构
心跳机制： 是否需要定期发送心跳？格式是什么？
消息确认： 是否需要发送 ACK？
研究方法：

查看 linyu 源码：NettyWebSocketServer.java、WebSocketService.java
或使用 linyu 客户端抓包分析
6.2 登录认证流程
linyu 使用 RSA 加密密码：


客户端请求公钥 → 获取 RSA 公钥 → 加密密码 → 发送登录请求
需要实现：

GET /v1/api/login/public-key 获取公钥
RSA 加密密码
POST /v1/api/login 登录
七、验证方案
7.1 单元测试

# 测试认证
python -c "from backend.adapters.linyu import LinyuAdapter; ..."

# 测试消息解析
pytest tests/test_linyu_adapter.py
7.2 集成测试
启动 Bot 服务
在 linyu 客户端发送消息给 AI 伴侣账号
验证 Bot 能够接收并回复
7.3 端到端测试
文本消息收发
图片消息收发
语音消息收发
断线重连
长时间运行稳定性
八、实施前准备
在 linyu 中注册 AI 伴侣账号

记录账号和密码
设置头像和昵称
添加好友关系

用你的账号添加 AI 伴侣为好友
或 AI 伴侣添加你为好友
确认 linyu 服务器地址

HTTP API 地址和端口
WebSocket 地址和端口
研究 linyu WebSocket 协议

查看源码或抓包分析
确认消息格式
九、风险与应对
风险	影响	应对措施
WebSocket 协议不明确	无法接收消息	查看 linyu 源码或抓包分析
RSA 加密实现复杂	登录失败	使用 Python cryptography 库
Token 过期	连接中断	实现 Token 刷新机制
消息格式变化	解析失败	添加容错处理
十、总结
本计划将 linyu IM 接入到 AI 伴侣项目，采用 WebSocket 直连方案，实现实时消息交互。相比 QQ 接入，无需中间层工具，可完全控制交互逻辑。

核心工作量：

新建 LinyuAdapter 类（约 800-1000 行，参考 QQAdapter）
修改配置文件和启动逻辑
研究 linyu WebSocket 协议
预期效果：

用户与 AI 伴侣账号私聊，体验更像真实伴侣
支持文本、图片、语音多模态交互
稳定可靠的长连接通信
