# 从 0 到 1 启动与参数配置教程

> 目标读者：第一次接手本项目的开发者/实施工程师。

## 1. 你会得到什么

完成本教程后，你可以：

1. 在本地拉起完整系统（前端 + 后端 + Celery + DB/Redis）。
2. 了解每个 `env` 文件该改什么、不该改什么。
3. 在云服务器按生产方式部署并完成基础验收。

## 2. 准备工作

- 操作系统：macOS / Linux
- 必需软件：`docker`、`node`、`python3.11`
- 推荐：先确保 3000、8000、5432、6379 端口不冲突

## 3. 本地启动（开发模式）

### Step 1. 拉代码并进入目录

```bash
git clone <your-repo-url>
cd <your-project-directory>
```

### Step 2. 复制环境变量模板

```bash
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env
```

### Step 3. 一键重启开发环境

```bash
bash scripts/ops.sh restart-dev
```

### Step 4. 首次初始化数据库（仅首次）

```bash
cd frontend
npm install
npm run prisma:migrate
npm run prisma:generate
npm run seed:auth
```

### Step 5. 验证服务

```bash
curl -i http://127.0.0.1:8000/health
```

浏览器访问：
- `http://127.0.0.1:3000`

## 4. 生产部署（云服务器）

### Step 1. 准备生产变量

```bash
cp .env.prod.example .env
```

修改 `.env` 的关键项：
- `NEXTAUTH_URL`
- `BACKEND_PUBLIC_BASE_URL`
- `DATABASE_URL`
- `REDIS_URL`
- `OBJECT_STORAGE_*`
- `NEXTAUTH_SECRET`
- `BACKEND_API_TOKEN`

### Step 2. 变量预检

```bash
bash scripts/ops.sh check-production-env
```

### Step 3. 部署

```bash
bash scripts/ops.sh deploy-production
```

### Step 4. 验收

```bash
bash scripts/verify.sh production
```

## 5. 参数修改教程（按场景）

## 5.1 场景 A：本地端口冲突

修改根目录 `.env`：

```dotenv
FRONTEND_PORT=3100
BACKEND_PORT=8100
PG_PORT=5433
REDIS_PORT=6380
```

然后重启：

```bash
bash scripts/ops.sh restart-dev
```

## 5.2 场景 B：切换 mock / 真实接口

修改 `backend/.env`：

```dotenv
HOOGENDOORN_PROVIDER=mock
# 或
HOOGENDOORN_PROVIDER=partner_api
HOOGENDOORN_SYSTEM_ID=REPLACE_WITH_SYSTEM_ID
HOOGENDOORN_METRIC_CATALOG_PATH=backend/data/hoogendoorn_metric_catalog.private.json
```

真实接口时，需补充：

```dotenv
HOOGENDOORN_CLIENT_ID=...
HOOGENDOORN_CLIENT_SECRET=...
HOOGENDOORN_SCOPE=external.partner.api
```

## 5.3 场景 C：生产对象存储切换

修改 `.env`：

```dotenv
FILE_STORAGE_BACKEND=object
OBJECT_STORAGE_ENDPOINT=...
OBJECT_STORAGE_REGION=...
OBJECT_STORAGE_BUCKET=...
OBJECT_STORAGE_ACCESS_KEY_ID=...
OBJECT_STORAGE_SECRET_ACCESS_KEY=...
OBJECT_STORAGE_PUBLIC_BASE_URL=...
```

## 5.4 场景 D：调整慢请求阈值

修改 `.env` 或 `backend/.env`：

```dotenv
SLOW_REQUEST_THRESHOLD_MS=1500
```

## 6. 注意事项（高频踩坑）

1. 不要把真实密钥提交 Git。
2. 生产环境不要用 `FILE_STORAGE_BACKEND=local`。
3. `BACKEND_INTERNAL_BASE_URL` 和 `BACKEND_PUBLIC_BASE_URL` 不要写反。
4. `NEXTAUTH_URL` 必须是用户实际访问域名（协议、域名、端口要一致）。
5. 发生“页面能开但 API 502”时，优先检查 `BACKEND_INTERNAL_BASE_URL`。

## 7. 故障排查速查

1. 后端起不来：`tail -f .devlogs/backend.log`
2. 前端起不来：`tail -f .devlogs/frontend.log`
3. Celery 异常：
   - `tail -f .devlogs/celery-worker.log`
   - `tail -f .devlogs/celery-beat.log`
4. 生产栈状态：

```bash
docker compose -f docker-compose.prod.yml ps
```

## 8. 推荐上线流程

1. 本地通过 `bash scripts/verify.sh regression`
2. 云端通过 `bash scripts/ops.sh check-production-env`
3. 云端执行 `bash scripts/ops.sh deploy-production`
4. 云端执行 `bash scripts/verify.sh production`
5. 人工抽检登录、Dashboard、Vision 三条核心链路

## 9. scripts 用法（非技术同事版）

这一节只讲“你要做什么”与“复制哪条命令”，不需要理解内部技术细节。

### 9.1 查看可用命令（先看这个）

```bash
bash scripts/ops.sh list
bash scripts/verify.sh list
```

### 9.2 本地环境有问题，一键重启

```bash
bash scripts/ops.sh restart-dev
```

用途：重启前端、后端、数据库、Redis、任务调度。

### 9.3 准备上线前，先检查参数

```bash
bash scripts/ops.sh check-production-env
```

用途：检查生产必填配置有没有漏填。

### 9.4 一键部署到服务器

```bash
bash scripts/ops.sh deploy-production
```

用途：按生产配置启动系统容器。

### 9.5 验收检查（最常用）

推荐 1：直接打开选择菜单（最简单）

```bash
bash scripts/verify.sh
```

推荐 2：直接跑“整体验收”

```bash
bash scripts/verify.sh full
```

如果你只想跑生产验收：

```bash
bash scripts/verify.sh production
```

### 9.6 手动刷新知识库（可选）

```bash
bash scripts/ops.sh harvest-knowledge
```

用途：立即更新一次知识库内容。

### 9.7 给常用同事的固定口诀

1. 本地异常：`restart-dev`
2. 上线前：`check-production-env`
3. 上线：`deploy-production`
4. 验收：`verify.sh`（菜单）或 `verify.sh full`
