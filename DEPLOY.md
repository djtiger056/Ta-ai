# Ta 部署说明（云服务器 / Linux）

项目目录：`/myproject/Ta`

当前已完成：
- 已拉取项目到 `/myproject/Ta`
- 已创建 Python 虚拟环境：`/myproject/Ta/.venv`
- 已安装后端依赖
- 已安装前端依赖并完成构建，产物目录：`/myproject/Ta/frontend/dist`
- 已补充可直接填写的配置模板：`/myproject/Ta/config.example.yaml`
- 已生成运行脚本：`/myproject/Ta/start.sh`
- 已生成 systemd 服务示例：`/myproject/Ta/deploy/ta.service`
- 已生成 Nginx 反代示例：`/myproject/Ta/deploy/nginx.ta.conf`
- 已修复 2 个会影响 Linux 启动的代码问题：
  - `backend/user/auth.py` 中 JWT 配置常量异常，现已修复
  - `backend/user/manager.py` 中 SQLite 相对路径在 Linux 下可能不稳，现已改为自动解析到项目绝对路径并自动建目录

## 一、你现在只要填这个文件

把下面文件复制成正式配置：

```bash
cd /myproject/Ta
cp config.example.yaml config.yaml
```

然后编辑：

`/myproject/Ta/config.yaml`

你最少需要改这几项：

### 1）服务安全项
- `jwt_secret_key`
- `admin.api_key`

建议都改成长随机字符串。

### 2）大模型配置（最关键）
在 `llm` 下至少填一套可用配置：
- `provider`
- `api_base`
- `api_key`
- `model`

默认模板里先放的是 OpenAI 兼容格式。

示例：

```yaml
llm:
  provider: openai
  api_base: https://api.openai.com/v1
  api_key: sk-xxxx
  model: gpt-4o-mini
```

如果你要接别的兼容接口，也直接改这里。

### 3）如果你要接 QQ / 语音 / 生图 / 视觉
默认我都先关掉了：
- `adapters.qq.enabled: false`
- `tts.enabled: false`
- `asr.enabled: false`
- `image_generation.enabled: false`
- `vision.enabled: false`
- `voice_gateway.enabled: false`

你后面按需开启，并填对应 provider 的 key。

这一步的好处是：
先保证项目“后端+前端+后台配置页”能跑起来，再逐项接能力。

## 二、启动方式

### 方式 A：先手动启动验证

后端：

```bash
cd /myproject/Ta
./start.sh
```

默认监听：
- 后端 API：`8003`

前端开发模式：

```bash
cd /myproject/Ta/frontend
npm run dev -- --host 0.0.0.0 --port 3000
```

前端已配置代理：
- `/api` -> `http://localhost:8003`

所以你可以直接访问：
- `http://你的服务器IP:3000`

### 方式 B：生产部署推荐

1. 后端用 systemd 守护
2. 前端用 Nginx 直接托管 `frontend/dist`
3. `/api` 反代到 `127.0.0.1:8003`

我已经给你生成好了示例文件：
- `/myproject/Ta/deploy/ta.service`
- `/myproject/Ta/deploy/nginx.ta.conf`

## 三、systemd 部署命令

如果你要直接上 systemd：

```bash
cp /myproject/Ta/deploy/ta.service /etc/systemd/system/ta.service
systemctl daemon-reload
systemctl enable ta
systemctl restart ta
systemctl status ta --no-pager
```

看日志：

```bash
journalctl -u ta -f
```

## 四、Nginx 部署命令

先确认机器上有 nginx，没有就安装：

```bash
apt update
apt install -y nginx
```

然后：

```bash
cp /myproject/Ta/deploy/nginx.ta.conf /etc/nginx/sites-available/ta
ln -sf /etc/nginx/sites-available/ta /etc/nginx/sites-enabled/ta
nginx -t
systemctl restart nginx
```

访问：
- `http://你的服务器IP`

## 五、我已经帮你验证过的内容

### 已验证 1：后端可以启动到“待填配置可用”状态
我已用模板配置启动并验证：
- `GET /` 正常返回
- `GET /api/config` 正常返回配置内容

说明：
- 服务框架能起来
- 配置读取正常
- 用户数据库初始化正常
- API 路由正常

注意：
因为你还没填真实 LLM key，所以“聊天调用模型”此时还不能真正出结果，这是预期行为。

### 已验证 2：前端可成功构建
已执行构建，`frontend/dist` 已生成。

### 已验证 3：前端静态文件可被 HTTP 服务正常提供
本地测试返回了 `200 OK`。

## 六、几个你后面可能会用到的文件

- 项目根目录：`/myproject/Ta`
- 配置模板：`/myproject/Ta/config.example.yaml`
- 正式配置：`/myproject/Ta/config.yaml`
- 启动脚本：`/myproject/Ta/start.sh`
- 后端服务文件：`/myproject/Ta/deploy/ta.service`
- Nginx 配置：`/myproject/Ta/deploy/nginx.ta.conf`

## 七、当前状态总结

现在已经到你要的状态了：

“部署到 `/myproject/` 下，并整理到只需要你填配置就能用”。

你现在只需要：
1. 编辑 `/myproject/Ta/config.yaml`
2. 填入真实 `llm api_key / model / api_base`
3. 改掉 `jwt_secret_key` 和 `admin.api_key`
4. 启动后端
5. 需要网页的话再配 Nginx

如果你要，我下一步可以继续直接帮你做这两件事之一：
1. 把 systemd + nginx 也直接在这台服务器上正式装好并启动
2. 按你准备用的模型平台，直接帮你把 `config.yaml` 填成可用版本
