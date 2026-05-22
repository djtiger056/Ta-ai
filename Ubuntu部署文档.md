# LFBot Ubuntu 服务器部署文档

这份文档面向已经在 Windows 本地跑通的场景，目标是在腾讯云 Ubuntu 服务器上快速上线。

## 一、部署方案

推荐方案：

- 后端：`systemd` 常驻运行
- 前端：`Nginx` 托管 `frontend/dist`
- 访问方式：浏览器访问 `http://你的服务器IP`
- 接口转发：`/api` 由 Nginx 反代到后端 `127.0.0.1:8003`

这个方案最简单，也最稳定。

## 二、服务器准备

先在腾讯云控制台放行这些端口：

- `22`：SSH
- `80`：网页访问
- `443`：如果后面要上 HTTPS

安装基础依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git build-essential ffmpeg
```

如果你的项目里有 `aiortc`、`av` 这类包，`ffmpeg` 和编译工具基本都要装。

## 三、上传项目

把项目上传到服务器，例如：

```bash
sudo mkdir -p /opt/lfbot
sudo chown -R $USER:$USER /opt/lfbot
```

然后把代码复制到 `/opt/lfbot`。

## 四、后端部署

进入项目目录：

```bash
cd /opt/lfbot
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

启动前先改 `config.yaml`：

- `server.debug: false`
- `server.host: 127.0.0.1`
- `server.port: 8003`

如果仓库里还没有 `config.yaml`，首次运行后端时会自动从 `config.example.yaml` 复制生成一份。

另外，`config.yaml` 里有 Windows 专用路径，需要改成 Linux 路径，重点看这里：

- `emotes.base_path`
- `emotes.categories[*].path`

建议改成类似：

```yaml
emotes:
  base_path: /opt/lfbot/backend/data/emotes
```

后续各分类路径也改成 `/opt/lfbot/backend/data/emotes/...`

后端启动命令：

```bash
source /opt/lfbot/venv/bin/activate
python /opt/lfbot/backend/main.py
```

## 五、前端部署

进入前端目录并构建：

```bash
cd /opt/lfbot/frontend
npm install
npm run build
```

构建成功后，会生成 `frontend/dist`。

注意：

- 项目里已经把登录/注册接口改成了相对路径 `/api`
- 前端其余请求本来就是走 `/api`
- 这样部署后不需要改前端接口地址

## 六、Nginx 配置

新建一个站点配置，例如：

```bash
sudo nano /etc/nginx/sites-available/lfbot
```

写入：

```nginx
server {
    listen 80;
    server_name _;

    root /opt/lfbot/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8003/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

启用站点并重载：

```bash
sudo ln -s /etc/nginx/sites-available/lfbot /etc/nginx/sites-enabled/lfbot
sudo nginx -t
sudo systemctl reload nginx
```

## 七、systemd 常驻服务

新建服务文件：

```bash
sudo nano /etc/systemd/system/lfbot.service
```

写入：

```ini
[Unit]
Description=LFBot Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/lfbot
ExecStart=/opt/lfbot/venv/bin/python /opt/lfbot/backend/main.py
Restart=always
RestartSec=5
Environment=PYTHONUTF8=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable lfbot
sudo systemctl start lfbot
sudo systemctl status lfbot
```

## 八、访问方式

浏览器直接访问：

```text
http://你的服务器公网IP
```

如果一切正常，你会看到前端页面，所有 `/api` 请求都会自动转到后端。

## 九、常用排查命令

看后端日志：

```bash
journalctl -u lfbot -f
```

看 Nginx 日志：

```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

检查端口占用：

```bash
ss -lntp | grep 8003
ss -lntp | grep 80
```

## 十、最小化流程

如果你只想快速跑起来，直接按这个顺序做：

1. 装依赖
2. 上传代码到 `/opt/lfbot`
3. 改 `config.yaml`
4. `pip install -r requirements.txt`
5. `npm run build`
6. 配 Nginx
7. 配 `systemd`

## 十一、注意事项

- `config.yaml` 里不要保留本地 Windows 路径
- 如果你不开 QQ / 语音适配器，先把对应模块关掉，便于首次上线
- 记得把真实密钥重新填到服务器上的 `config.yaml`
- 生产环境建议后面再补 HTTPS
