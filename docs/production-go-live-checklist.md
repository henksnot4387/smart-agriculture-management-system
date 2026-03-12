# 云端部署参数清单与上线验收清单

## 1. 目的

在云端执行部署时，先完成参数核对，再执行部署与验收，避免“容器起来但链路不可用”。

## 2. 参数清单（必须）

### 2.1 基础与网关

| 变量 | 示例 | 说明 |
|---|---|---|
| `APP_ENV` | `production` | 生产模式 |
| `NGINX_HTTP_PORT` | `80` | 网关 HTTP 端口 |
| `NEXTAUTH_URL` | `https://farm.example.com` | 前端公开访问地址 |
| `NEXTAUTH_SECRET` | `***` | NextAuth 密钥 |
| `BACKEND_API_TOKEN` | `***` | 后端内网令牌（API + WS） |
| `BACKEND_INTERNAL_BASE_URL` | `http://backend:8000` | 前端容器内访问后端 |
| `BACKEND_PUBLIC_BASE_URL` | `https://farm.example.com` | 浏览器侧公开地址（WS URL 使用） |

### 2.2 外部依赖（不内置容器）

| 变量 | 示例 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | 外部 PG/Timescale 连接串 |
| `REDIS_URL` | `redis://...` | 外部 Redis 连接串 |

### 2.3 对象存储（生产必填）

| 变量 | 示例 | 说明 |
|---|---|---|
| `FILE_STORAGE_BACKEND` | `object` | 生产固定对象存储 |
| `OBJECT_STORAGE_ENDPOINT` | `https://s3.ap-east-1.amazonaws.com` | S3 兼容端点 |
| `OBJECT_STORAGE_REGION` | `ap-east-1` | 区域 |
| `OBJECT_STORAGE_BUCKET` | `intellifarm-prod` | 桶名 |
| `OBJECT_STORAGE_ACCESS_KEY_ID` | `***` | Access Key |
| `OBJECT_STORAGE_SECRET_ACCESS_KEY` | `***` | Secret Key |
| `OBJECT_STORAGE_PUBLIC_BASE_URL` | `https://cdn.example.com` | 公网读取前缀 |
| `OBJECT_STORAGE_PREFIX` | `vision/` | 对象前缀（可选） |
| `OBJECT_STORAGE_FORCE_PATH_STYLE` | `true` | 路径风格（按供应商调整） |

### 2.4 可选（建议）

| 变量 | 示例 | 说明 |
|---|---|---|
| `BACKEND_ADMIN_TOKEN` | `***` | 手动同步接口令牌 |
| `SLOW_REQUEST_THRESHOLD_MS` | `1000` | 慢请求阈值 |
| `DEEPSEEK_API_KEY` | `***` | AI 建议增强 |
| `HOOGENDOORN_PROVIDER` | `partner_api` | 真实环境建议 |

## 3. 上线步骤

1. 预检变量  
   `bash scripts/ops.sh check-production-env`

2. 构建并启动  
   `bash scripts/ops.sh deploy-production`

3. 自动验收  
   `bash scripts/verify.sh production`

4. 人工抽检
   - 访问 `/` 页面加载正常
   - 登录后 `/dashboard` 可取数
   - `/vision` 上传后任务可进入 `PROCESSING -> DONE/FAILED`
   - `/scheduler`（SUPER_ADMIN）可访问

## 4. 验收清单（Go/No-Go）

- [ ] `bash scripts/ops.sh check-production-env` 全部 PASS  
- [ ] `bash scripts/ops.sh deploy-production` 无报错  
- [ ] `bash scripts/verify.sh production` 全部 PASS  
- [ ] `/backend-health` = 200  
- [ ] Vision WS 路径探测可达  
- [ ] 登录态、Dashboard、Vision 三条核心链路通过  
- [ ] 调度中心与可观测中心可访问（SUPER_ADMIN）  

## 5. 常见失败与处理

1. `backend` 启动失败，日志提示对象存储配置缺失  
   - 检查 `OBJECT_STORAGE_*` 是否完整，`FILE_STORAGE_BACKEND` 是否为 `object`。

2. 登录后 API 大量 502  
   - 检查 `BACKEND_INTERNAL_BASE_URL` 是否仍为容器内地址（建议 `http://backend:8000`）。

3. Vision WebSocket 连接失败  
   - 检查 `BACKEND_PUBLIC_BASE_URL` 是否为浏览器可达域名。
   - 检查 Nginx `/api/ws/vision/tasks` upgrade 转发是否生效。

4. `bash scripts/verify.sh production` 报 nginx unhealthy  
   - 检查 80 端口是否冲突，或修改 `NGINX_HTTP_PORT`。

## 6. 回滚步骤

1. 保留旧镜像 tag（建议上线前打 tag）。  
2. 回滚 compose 镜像版本后执行：  
   `docker compose -f docker-compose.prod.yml up -d`  
3. 重新执行：  
   `bash scripts/verify.sh production`  
4. 若仍失败，先恢复旧版本前端+后端，再逐个恢复 celery 组件。
