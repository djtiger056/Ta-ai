# images-api 视频外部接入模板

这份文档面向外部业务系统接入，重点是可复制的前端 / 后端模板。

推荐接入顺序：

1. 豆包免费额度验证链路：`doubao-seedance-2.0-fast`
2. 千问 Wan 正式视频链路：`wan2.7-t2v`
3. 即梦长任务链路：`/v1/videos/generations/async`

## 1. 重要规则

### 1.1 图生视频不支持修改视频比例

当请求里传了 `images`，即图生视频 / 首帧参考图视频时，外部接入方不要传 `ratio`。

原因：

- `images-api` 会读取首张参考图尺寸，并自动推断最接近的视频比例。
- `ratio` 只对文生视频生效。
- 如果业务需要固定输出 `9:16`、`16:9` 等比例，请先把参考图裁剪、扩展或补边到目标比例，再传给接口。

错误示例：

```json
{
  "model": "wan2.7-t2v",
  "prompt": "让人物缓慢转头",
  "ratio": "9:16",
  "images": ["https://cdn.example.com/source-16x9.jpg"]
}
```

正确示例：

```json
{
  "model": "wan2.7-t2v",
  "prompt": "让人物缓慢转头",
  "images": ["https://cdn.example.com/source-9x16.jpg"]
}
```

### 1.2 凭证不要暴露给普通浏览器用户

推荐架构：

```text
Browser -> Your Backend -> images-api -> upstream provider
```

只有内网工具、受控管理后台、临时测试页面，才建议浏览器直连 `images-api`。

### 1.3 统一结果字段

同步视频接口成功时至少会返回：

```json
{
  "created": 1710000000,
  "data": [
    { "url": "https://example.com/result.mp4" }
  ],
  "model": "wan2.7-t2v",
  "provider": "qwen"
}
```

失败时通常返回：

```json
{
  "created": 1710000000,
  "error": {
    "message": "视频生成失败",
    "type": "generation_failed"
  }
}
```

业务侧请优先读取 `data[0].url`，并兼容 `videoUrl`、`result_url`、`videoUrls[0]`。

## 2. 支持模型

### 2.1 推荐模型矩阵

| 模型 | 端点 | 凭证 | 文生视频 | 图生视频 | 比例 | 清晰度 | 时长 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `doubao-seedance-2.0-fast` | `/v1/doubao/videos/generations` | Doubao `sessionid` | 支持 | 支持参考图 | 文生可传；图生自动按首图 | 固定上游能力 | 固定 5 秒 |
| `qwen-happyhorse-1.0` | `/v1/qwen/videos/generations` | Qwen Cookie | 支持 | 不支持 | 文生可传 | `720P` | 5 / 10 秒 |
| `wan2.6-t2v` | `/v1/qwen/videos/generations` | Qwen Cookie 或 DashScope Key 配置 | 支持 | 不支持 | 文生可传 | `720P` / `1080P` | 2-15 秒 |
| `wan2.7-t2v` | `/v1/qwen/videos/generations` | Qwen Cookie | 支持 | 支持首帧参考图 | 文生可传；图生自动按首图 | `720P` / `1080P` | 2-15 秒 |
| `wan2.7-t2v-2026-04-25` | `/v1/qwen/videos/generations` | Qwen Cookie | 支持 | 支持首帧参考图 | 文生可传；图生自动按首图 | `720P` / `1080P` | 2-15 秒 |
| `jimeng-video-3.5-pro` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持首尾帧 | 按即梦能力 | `720p` / `1080p` | 5 / 10 秒 |
| `jimeng-video-3.0-pro` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持首尾帧 | 按即梦能力 | `720p` / `1080p` | 5 / 10 秒 |
| `jimeng-video-3.0` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持首尾帧 | 按即梦能力 | `720p` / `1080p` | 5 / 10 秒 |
| `jimeng-video-seedance-2.0` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持素材输入 | 按即梦能力 | 按上游能力 | 4-15 秒 |
| `jimeng-video-seedance-2.0-fast` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持素材输入 | 按即梦能力 | 按上游能力 | 4-15 秒 |
| `jimeng-video-seedance-2.0-fast-vip` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持素材输入 | 按账号权限 | 会员能力 | 4-15 秒 |
| `jimeng-video-seedance-2.0-vip` | `/v1/videos/generations` 或 async | Jimeng `sessionid` | 支持 | 支持素材输入 | 按账号权限 | 会员能力 | 4-15 秒 |

### 2.2 接入选择建议

- 免费体验：优先 `doubao-seedance-2.0-fast`，但注意每日额度。
- 正式文生视频：优先 `wan2.7-t2v`。
- 首帧参考图视频：优先 `wan2.7-t2v` 或 `doubao-seedance-2.0-fast`。
- 需要异步任务、恢复轮询或较长等待：使用 `/v1/videos/generations/async`。

## 3. 通用配置

```ts
const API_BASE_URL = "http://127.0.0.1:18080";
const API_KEY = "your-images-api-key";
const DOUBAO_TOKEN = "your-doubao-sessionid";
const QWEN_COOKIE = "your-qwen-cookie";
const JIMENG_TOKEN = "your-jimeng-sessionid";
```

说明：

- `API_KEY` 只有在服务端配置了 `SERVER_API_KEY` 或 `SERVER_API_KEYS` 时才需要。
- 上游凭证已配置在 `images-api` 服务端环境变量时，请求侧可以不传 `Authorization`。
- 请求侧传上游凭证时统一使用 `Authorization: Bearer xxx`。

## 4. 前端通用模板

### 4.1 请求封装

```ts
type VideoApiResult =
  | { ok: true; url: string; urls: string[]; raw: any }
  | { ok: false; message: string; errorType?: string; raw: any };

async function postJson(
  path: string,
  body: Record<string, any>,
  extraHeaders: Record<string, string> = {}
) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };

  if (API_KEY) headers["x-api-key"] = API_KEY;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    return {
      error: data?.error || { message: data?.message || res.statusText },
      raw: data,
    };
  }

  return data;
}

function normalizeVideoResult(data: any): VideoApiResult {
  if (data?.error) {
    return {
      ok: false,
      message: data.error.message || data.message || "视频生成失败",
      errorType: data.error.type,
      raw: data,
    };
  }

  const urls = [
    data?.data?.[0]?.url,
    data?.videoUrl,
    data?.result_url,
    ...(Array.isArray(data?.videoUrls) ? data.videoUrls : []),
  ].filter(Boolean);

  const uniqueUrls = Array.from(new Set(urls));

  if (!uniqueUrls.length) {
    return {
      ok: false,
      message: "接口未返回视频地址",
      raw: data,
    };
  }

  return {
    ok: true,
    url: uniqueUrls[0],
    urls: uniqueUrls,
    raw: data,
  };
}

function authHeader(token?: string) {
  if (!token) return {};
  return {
    Authorization: token.startsWith("Bearer ") ? token : `Bearer ${token}`,
  };
}
```

### 4.2 构造 payload

这个函数会强制执行“图生视频不传 `ratio`”。

```ts
type VideoModel =
  | "doubao-seedance-2.0-fast"
  | "qwen-happyhorse-1.0"
  | "wan2.6-t2v"
  | "wan2.7-t2v"
  | "wan2.7-t2v-2026-04-25";

type BuildVideoPayloadParams = {
  model: VideoModel;
  prompt: string;
  ratio?: "16:9" | "9:16" | "1:1" | "4:3" | "3:4";
  resolution?: "720P" | "1080P";
  duration?: number;
  images?: string[];
};

function buildVideoPayload(params: BuildVideoPayloadParams) {
  const images = (params.images || []).filter(Boolean);
  const body: Record<string, any> = {
    model: params.model,
    prompt: params.prompt,
    response_format: "url",
  };

  if (params.duration) body.duration = params.duration;
  if (params.resolution) body.resolution = params.resolution;

  if (images.length > 0) {
    body.images = images;
  } else {
    body.ratio = params.ratio || "16:9";
  }

  return body;
}
```

### 4.3 豆包文生视频

```ts
async function generateDoubaoTextVideo(prompt: string) {
  const data = await postJson(
    "/v1/doubao/videos/generations",
    buildVideoPayload({
      model: "doubao-seedance-2.0-fast",
      prompt,
      ratio: "16:9",
      duration: 5,
    }),
    authHeader(DOUBAO_TOKEN)
  );

  return normalizeVideoResult(data);
}
```

### 4.4 豆包参考图视频

注意：这里不传 `ratio`，输出比例跟随首张参考图。

```ts
async function generateDoubaoImageVideo(prompt: string, imageUrl: string) {
  const data = await postJson(
    "/v1/doubao/videos/generations",
    buildVideoPayload({
      model: "doubao-seedance-2.0-fast",
      prompt,
      duration: 5,
      images: [imageUrl],
    }),
    authHeader(DOUBAO_TOKEN)
  );

  return normalizeVideoResult(data);
}
```

### 4.5 Wan 2.7 文生视频

```ts
async function generateWan27TextVideo(prompt: string) {
  const data = await postJson(
    "/v1/qwen/videos/generations",
    buildVideoPayload({
      model: "wan2.7-t2v",
      prompt,
      ratio: "16:9",
      resolution: "1080P",
      duration: 5,
    }),
    authHeader(QWEN_COOKIE)
  );

  return normalizeVideoResult(data);
}
```

### 4.6 Wan 2.7 首帧参考图视频

注意：这里不传 `ratio`。如果要 `9:16` 输出，请先把 `imageUrl` 对应图片处理成 `9:16`。

```ts
async function generateWan27ImageVideo(prompt: string, imageUrl: string) {
  const data = await postJson(
    "/v1/qwen/videos/generations",
    buildVideoPayload({
      model: "wan2.7-t2v",
      prompt,
      resolution: "1080P",
      duration: 5,
      images: [imageUrl],
    }),
    authHeader(QWEN_COOKIE)
  );

  return normalizeVideoResult(data);
}
```

### 4.7 页面渲染示例

```ts
async function onSubmit() {
  const result = await generateWan27TextVideo(
    "一只白猫在窗边回头看向镜头，晨光柔和"
  );

  if (!result.ok) {
    alert(result.message);
    return;
  }

  const video = document.querySelector("video");
  if (video) {
    video.src = result.url;
    video.controls = true;
    video.load();
  }
}
```

## 5. 后端 Node.js 模板

Node 18+ 可以直接使用内置 `fetch`。

```ts
type GenerateVideoParams = {
  model: string;
  prompt: string;
  ratio?: string;
  duration?: number;
  resolution?: string;
  images?: string[];
  authorization?: string;
};

type GenerateVideoResponse =
  | { ok: true; url: string; urls: string[]; raw: any }
  | { ok: false; message: string; errorType?: string; raw: any };

const API_BASE_URL = process.env.IMAGES_API_BASE_URL || "http://127.0.0.1:18080";
const API_KEY = process.env.IMAGES_API_KEY || "";

async function callImagesApi(path: string, body: Record<string, any>, authorization?: string) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (API_KEY) headers["x-api-key"] = API_KEY;
  if (authorization) {
    headers["Authorization"] = authorization.startsWith("Bearer ")
      ? authorization
      : `Bearer ${authorization}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const data = await res.json();

  if (!res.ok) {
    return {
      error: data?.error || { message: data?.message || res.statusText },
      raw: data,
    };
  }

  return data;
}

function parseVideoResponse(data: any): GenerateVideoResponse {
  if (data?.error) {
    return {
      ok: false,
      message: data.error.message || data.message || "视频生成失败",
      errorType: data.error.type,
      raw: data,
    };
  }

  const urls = [
    data?.data?.[0]?.url,
    data?.videoUrl,
    data?.result_url,
    ...(Array.isArray(data?.videoUrls) ? data.videoUrls : []),
  ].filter(Boolean);

  const uniqueUrls = Array.from(new Set(urls));

  if (!uniqueUrls.length) {
    return {
      ok: false,
      message: "接口未返回视频地址",
      raw: data,
    };
  }

  return {
    ok: true,
    url: uniqueUrls[0],
    urls: uniqueUrls,
    raw: data,
  };
}

function buildTextToVideoBody(params: GenerateVideoParams) {
  return {
    model: params.model,
    prompt: params.prompt,
    ratio: params.ratio || "16:9",
    duration: params.duration,
    resolution: params.resolution,
    response_format: "url",
  };
}

function buildImageToVideoBody(params: GenerateVideoParams) {
  const images = (params.images || []).filter(Boolean);
  if (!images.length) {
    throw new Error("图生视频至少需要一张参考图");
  }

  return {
    model: params.model,
    prompt: params.prompt,
    duration: params.duration,
    resolution: params.resolution,
    images,
    response_format: "url",
  };
}
```

### 5.1 后端豆包服务

```ts
export async function generateDoubaoVideo(params: {
  prompt: string;
  ratio?: "16:9" | "9:16" | "1:1" | "4:3" | "3:4";
  images?: string[];
}) {
  const hasImages = Boolean(params.images?.length);
  const body = hasImages
    ? buildImageToVideoBody({
        model: "doubao-seedance-2.0-fast",
        prompt: params.prompt,
        duration: 5,
        images: params.images,
      })
    : buildTextToVideoBody({
        model: "doubao-seedance-2.0-fast",
        prompt: params.prompt,
        ratio: params.ratio || "16:9",
        duration: 5,
      });

  const data = await callImagesApi(
    "/v1/doubao/videos/generations",
    body,
    process.env.DOUBAO_TOKEN
  );

  return parseVideoResponse(data);
}
```

### 5.2 后端 Qwen / Wan 服务

```ts
export async function generateQwenVideo(params: {
  model: "qwen-happyhorse-1.0" | "wan2.6-t2v" | "wan2.7-t2v" | "wan2.7-t2v-2026-04-25";
  prompt: string;
  ratio?: "16:9" | "9:16" | "1:1" | "4:3" | "3:4";
  duration?: number;
  resolution?: "720P" | "1080P";
  images?: string[];
}) {
  const hasImages = Boolean(params.images?.length);

  if (hasImages && !params.model.startsWith("wan2.7")) {
    return {
      ok: false as const,
      message: `${params.model} 不支持图生视频，请改用 wan2.7-t2v`,
      raw: null,
    };
  }

  const body = hasImages
    ? buildImageToVideoBody({
        model: params.model,
        prompt: params.prompt,
        duration: params.duration || 5,
        resolution: params.resolution || "1080P",
        images: params.images,
      })
    : buildTextToVideoBody({
        model: params.model,
        prompt: params.prompt,
        ratio: params.ratio || "16:9",
        duration: params.duration || 5,
        resolution: params.resolution || "1080P",
      });

  const data = await callImagesApi(
    "/v1/qwen/videos/generations",
    body,
    process.env.QWEN_COOKIE
  );

  return parseVideoResponse(data);
}
```

### 5.3 Express 路由示例

```ts
import express from "express";

const app = express();
app.use(express.json({ limit: "20mb" }));

app.post("/api/video/doubao", async (req, res) => {
  const result = await generateDoubaoVideo({
    prompt: req.body.prompt,
    ratio: req.body.ratio,
    images: req.body.images,
  });

  if (!result.ok) return res.status(400).json(result);
  return res.json(result);
});

app.post("/api/video/qwen", async (req, res) => {
  const result = await generateQwenVideo({
    model: req.body.model || "wan2.7-t2v",
    prompt: req.body.prompt,
    ratio: req.body.ratio,
    duration: req.body.duration,
    resolution: req.body.resolution,
    images: req.body.images,
  });

  if (!result.ok) return res.status(400).json(result);
  return res.json(result);
});
```

## 6. Axios 模板

```ts
import axios from "axios";

const client = axios.create({
  baseURL: process.env.IMAGES_API_BASE_URL || "http://127.0.0.1:18080",
  timeout: 10 * 60 * 1000,
});

client.interceptors.request.use((config) => {
  const headers = config.headers || {};
  if (process.env.IMAGES_API_KEY) {
    headers["x-api-key"] = process.env.IMAGES_API_KEY;
  }
  config.headers = headers;
  return config;
});

function buildAuthHeader(token?: string) {
  if (!token) return {};
  return {
    Authorization: token.startsWith("Bearer ") ? token : `Bearer ${token}`,
  };
}

function unwrapVideoResult(data: any) {
  const result = parseVideoResponse(data);
  if (!result.ok) {
    throw new Error(result.message);
  }
  return result.url;
}
```

Wan 2.7 文生视频：

```ts
export async function generateWan27VideoByAxios(prompt: string) {
  const { data } = await client.post(
    "/v1/qwen/videos/generations",
    buildTextToVideoBody({
      model: "wan2.7-t2v",
      prompt,
      ratio: "16:9",
      resolution: "1080P",
      duration: 5,
    }),
    {
      headers: buildAuthHeader(process.env.QWEN_COOKIE),
    }
  );

  return unwrapVideoResult(data);
}
```

Wan 2.7 首帧参考图视频：

```ts
export async function generateWan27ImageVideoByAxios(prompt: string, imageUrl: string) {
  const { data } = await client.post(
    "/v1/qwen/videos/generations",
    buildImageToVideoBody({
      model: "wan2.7-t2v",
      prompt,
      resolution: "1080P",
      duration: 5,
      images: [imageUrl],
    }),
    {
      headers: buildAuthHeader(process.env.QWEN_COOKIE),
    }
  );

  return unwrapVideoResult(data);
}
```

豆包文生视频：

```ts
export async function generateDoubaoVideoByAxios(prompt: string) {
  const { data } = await client.post(
    "/v1/doubao/videos/generations",
    buildTextToVideoBody({
      model: "doubao-seedance-2.0-fast",
      prompt,
      ratio: "16:9",
      duration: 5,
    }),
    {
      headers: buildAuthHeader(process.env.DOUBAO_TOKEN),
    }
  );

  return unwrapVideoResult(data);
}
```

## 7. 异步任务轮询模板

适合即梦视频和 Seedance 长任务：

- `POST /v1/videos/generations/async`
- `GET /v1/videos/generations/async/:taskId`

### 7.1 提交任务

```ts
async function submitAsyncVideoTask() {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${JIMENG_TOKEN}`,
  };

  if (API_KEY) headers["x-api-key"] = API_KEY;

  const res = await fetch(`${API_BASE_URL}/v1/videos/generations/async`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: "jimeng-video-3.5-pro",
      prompt: "一个女孩在海边回头微笑，镜头平稳推进",
      ratio: "16:9",
      resolution: "1080p",
      duration: 5,
    }),
  });

  return res.json();
}
```

### 7.2 轮询查询

```ts
function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function queryAsyncVideoTask(taskId: string) {
  const headers: Record<string, string> = {};
  if (API_KEY) headers["x-api-key"] = API_KEY;

  const res = await fetch(`${API_BASE_URL}/v1/videos/generations/async/${taskId}`, {
    method: "GET",
    headers,
  });

  return res.json();
}

async function waitForVideoResult(taskId: string, timeoutMs = 8 * 60 * 1000) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const data = await queryAsyncVideoTask(taskId);
    const urls = [
      data?.data?.[0]?.url,
      data?.videoUrl,
      data?.result_url,
      ...(Array.isArray(data?.videoUrls) ? data.videoUrls : []),
    ].filter(Boolean);

    if (urls.length > 0) {
      return {
        ok: true,
        url: urls[0],
        urls: Array.from(new Set(urls)),
        raw: data,
      };
    }

    if (data?.status === "failed" || data?.error) {
      return {
        ok: false,
        message: data?.error?.message || data?.message || "异步视频任务失败",
        raw: data,
      };
    }

    await sleep(4000);
  }

  return {
    ok: false,
    message: "视频生成超时",
    raw: null,
  };
}
```

## 8. 推荐业务接口

前端页面建议只请求你们自己的业务后端：

```http
POST /api/video/generate
Content-Type: application/json
```

文生视频：

```json
{
  "provider": "qwen",
  "model": "wan2.7-t2v",
  "prompt": "一只白猫在窗边回头看向镜头，晨光柔和",
  "ratio": "16:9",
  "duration": 5,
  "resolution": "1080P"
}
```

图生视频：

```json
{
  "provider": "qwen",
  "model": "wan2.7-t2v",
  "prompt": "保持人物一致，让她缓慢转头看向镜头",
  "duration": 5,
  "resolution": "1080P",
  "images": [
    "https://your-cdn.example.com/first-frame-9x16.jpg"
  ]
}
```

统一返回：

```json
{
  "ok": true,
  "url": "https://example.com/result.mp4"
}
```

失败：

```json
{
  "ok": false,
  "message": "豆包视频今日免费额度已用完（每日10次），请明天再试。"
}
```

## 9. 错误处理规则

最低限度需要处理：

1. 返回 `error` 时按失败处理。
2. 没有 `data[0].url`、`videoUrl`、`result_url`、`videoUrls[0]` 时按失败处理。
3. `quota_exhausted` 单独提示“今日额度用完”。
4. 同步请求建议前端超时设置为 5-10 分钟。
5. 异步轮询建议每 3-5 秒查一次，总超时 8-10 分钟。
6. 图生视频不要提供“选择输出比例”的 UI，只提示“输出比例跟随首张参考图”。
