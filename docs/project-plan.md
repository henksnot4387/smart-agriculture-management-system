# 智慧农业管理系统执行计划

> 更新（2026-03-10）：`AI 摘要解读` 已升级并统一命名为 `AI 智能解析`。主路径切换为 `/ai-insights` 与 `/api/ai-insights/*`，旧 `/copilot` 与 `/api/copilot/*` 保留兼容映射。
>
> 更新（2026-03-11）：已落地“真实数据 + 专业解析 + 任务自动化”第一版：
> - 新增参数主数据目录（开源版请使用示例文件或私有覆盖文件）
> - 新增长格式时序样本表 `ops_metric_samples` 与 `/api/ops/catalog|live|trends`
> - 首页已接入 `ops live` 模块（执行器/锅炉/气象站/水肥状态）
> - AI 智能解析新增 `DeepSeek -> 本地LLM -> 规则引擎` 三级兜底
> - 新增四类设置接口与页面：园艺 / 植保 / 环控 / 水肥（支持自动任务触发）

## 1. 项目任务清单

说明：
- 优先级：`P0` 必做、`P1` 重要、`P2` 增强
- 工期：按单人全栈估算，可并行时可缩短

| 阶段 | 任务 | 优先级 | 预估工期 | 代码目录 | 验收标准 |
|---|---|---|---|---|---|
| 项目初始化 | 初始化仓库结构与基础脚本 | P0 | 0.5 天 | `frontend/` `backend/` `scripts/` 根目录 | 目录结构与白皮书一致；当前统一入口脚本为 `scripts/ops.sh restart-dev` |
| 中间件编排 | 本地中间件编排（PostgreSQL+TimescaleDB+Redis） | P0 | 0.5 天 | `docker-compose.yml` | `docker-compose up -d` 后 5432/6379 可连通，Timescale 扩展启用成功 |
| 环境配置管理 | 环境变量与密钥管理 | P0 | 0.5 天 | `.env.example` `frontend/.env.local` `backend/.env` | 所有服务无硬编码密钥；缺失变量时启动报错清晰 |
| 核心数据模型 | Prisma 数据模型（SensorData/Task/User/Detection） | P0 | 1 天 | `frontend/prisma/schema.prisma` | `prisma migrate` 成功；任务状态含 `PENDING/APPROVED/IN_PROGRESS/COMPLETED` |
| 登录鉴权 | NextAuth 登录鉴权最小闭环 | P0 | 1 天 | `frontend/src/app/(auth)` `frontend/src/lib/auth` | 可登录/登出；未登录访问业务页会重定向 |
| 后端骨架 | FastAPI 项目骨架与健康检查 | P0 | 0.5 天 | `backend/app` | `/health` 返回 200；日志与异常处理中间件可用 |
| 数据接入与重试 | Hoogendoorn 数据接入模拟器 + tenacity 重试 | P0 | 1 天 | `backend/app/integrations/hoogendoorn` | 断网后指数退避重试；恢复后可补录断线区间数据 |
| 传感器查询接口 | 传感器数据写入与查询 API | P0 | 1 天 | `backend/app/api/sensor` | 前端可按时间区间拉取温湿度/EC/pH 时序数据 |
| 管理首页 | Dashboard 首版（核心卡片+时序图） | P0 | 1.5 天 | `frontend/src/app/(system)/dashboard` `frontend/src/components/charts` | 页面可实时展示核心指标；图表可切换 24h/7d |
| 视觉推理 | YOLOv8 推理服务（mps 优先，cpu 回退） | P0 | 1.5 天 | `backend/app/ai/vision` | Apple Silicon 下默认 `mps`；不支持算子时自动回退 `cpu` |
| 异步识别队列 | 图片异步识别队列（Redis+BackgroundTasks） | P0 | 1 天 | `backend/app/workers` `backend/app/api/vision` | 上传后立即返回“已受理”；后台完成后状态可查询 |
| 结果实时回传 | 识别结果回传（WebSocket/轮询二选一） | P1 | 1 天 | `backend/app/api/ws` `frontend/src/app/vision` | 前端可看到任务从 `PROCESSING` 到 `DONE/FAILED` 的状态变化 |
| AI摘要 | AI Copilot 摘要聚合器（24h 降维） | P0 | 1 天 | `backend/app/ai/summary` | 万级记录可在可接受时间内生成摘要文本（含极值、异常时长、病害次数） |
| 摘要收口与调度中心 | 摘要收口 + 调度中心 + 知识采集增强 | P0 | 1.5 天 | `backend/app/scheduler` `frontend/src/app/(system)/scheduler` | `SUPER_ADMIN` 可管理调度任务；摘要主入口为 `/ai-insights`（兼容 `/copilot`）；知识采集可观测 |
| AI建议入库 | DeepSeek 调用与建议入库（默认 PENDING） | P0 | 1 天 | `backend/app/ai/copilot` `backend/app/api/copilot` | 对话返回建议草稿并确认入库；任务状态默认 `PENDING` |
| 专家审批 | 专家审批台（PENDING -> APPROVED） | P0 | 1 天 | `frontend/src/app/expert` | 专家可筛选待审任务并一键 Approve，状态实时更新 |
| 工人执行 | 工人端 PWA 任务流（接单/上传/完工） | P0 | 1.5 天 | `frontend/src/app/worker` `frontend/public` | 手机竖屏可用；完成 `APPROVED -> IN_PROGRESS -> COMPLETED` 闭环 |
| 时序策略 | 时序降采样与保留策略（Timescale policy） | P1 | 1 天 | `backend/app/db/policies` | 秒级/15分钟/日均分层策略生效；历史查询性能稳定 |
| 可观测性 | 可观测性与告警（日志、错误、慢任务） | P1 | 1 天 | `backend/app/core/logging` `frontend/src/lib/monitoring` | 关键链路有结构化日志；识别失败与外部 API 失败可追踪 |
| 联调回归 | 端到端联调与回归测试 | P0 | 1.5 天 | `frontend/tests` `backend/tests` | 覆盖登录、数据看板、AI建议、审批、工人执行全链路 |
| 生产部署 | 生产容器化与部署脚本 | P1 | 1 天 | `frontend/Dockerfile` `backend/Dockerfile` `docker-compose.prod.yml` | 一条命令完成云端启动；健康检查通过 |

## 1.1 当前完成状态（截至 2026-03-07）

| 阶段 | 状态 | 验收结果 | 验收备注 |
|---|---|---|---|
| 项目初始化 | 已完成 | 通过 | 目录结构与白皮书一致；历史启动脚本已收敛，当前统一使用 `scripts/ops.sh restart-dev` |
| 中间件编排 | 已完成 | 通过 | `docker compose up -d` 后 PostgreSQL/Redis 可用；TimescaleDB 扩展启用成功 |
| 环境配置管理 | 已完成 | 通过 | 根目录、前端、后端环境变量模板已补齐；缺失变量时启动报错清晰 |
| 核心数据模型 | 已完成 | 通过 | Prisma 初始迁移成功；Timescale hypertable 已创建；`TaskStatus` 包含 `PENDING/APPROVED/IN_PROGRESS/COMPLETED` |
| 登录鉴权 | 已完成 | 通过 | NextAuth 最小闭环已实现；支持登录/登出；未登录访问业务页会重定向 |
| 后端骨架 | 已完成 | 通过 | FastAPI 项目骨架已建立；`/health` 返回 200；请求日志与异常处理中间件已接入 |
| 数据接入与重试 | 已完成 | 通过 | Mock 模拟器、真实 Partner API provider 骨架、tenacity 指数退避重试、断线补录与 `sensor_data` 入库链路已完成；时间约定已固定为“UTC 无时区字符串 + utcOffset 元数据” |
| 传感器查询接口 | 已完成 | 通过 | 已新增 `/api/sensor/raw`、`/api/sensor/series`、`/api/sensor/dashboard`；支持时区感知时间输入、Timescale 聚合、raw unpivot、zone/metric 过滤与空区间安全返回；已收口为 `X-API-Token` 内网令牌模式（受保护接口统一强制配置） |
| 管理首页 | 已完成 | 通过 | 已重构为中文“智慧农业管理系统”首页；具备左侧菜单壳子、24h/7d 切换、4 张核心指标卡片、4 张趋势图、温室分区态势、30 秒轮询及内部代理 `/api/dashboard/sensor`、`/api/dashboard/zones`；当前已对接真实 Hoogendoorn 实例名称并默认展示激活 provider 数据 |
| 视觉推理 | 已完成 | 通过 | 已新增视觉推理引擎抽象（`auto/yolo/mock`），`auto` 默认优先 YOLO 并在依赖缺失或运行失败时自动回退 mock/cpu；新增 `/api/vision/runtime` 可验证 `engine/device/storageBackend` |
| 异步识别队列 | 已完成 | 通过 | 已新增 `/api/vision/tasks` 异步受理与 Redis 队列消费链路；任务状态可从 `PROCESSING -> DONE/FAILED` 查询；`/vision` 页面已支持上传与 3 秒轮询展示结果 |
| 结果实时回传 | 已完成 | 通过 | 已新增 `GET /api/vision/ws-url` 与后端 `WS /api/ws/vision/tasks` 实时推送；`/vision` 页面已移除 3 秒高频轮询并改为事件增量更新，任务状态可实时从 `PROCESSING` 切换到 `DONE/FAILED` |
| AI摘要 | 已完成 | 通过 | 已新增 `GET /api/ai-insights/summary`（兼容 `/api/copilot/summary`）与 `knowledge` 知识库接口；输出极值、异常时长、病害次数与摘要文案；摘要主展示页为 `/ai-insights`（兼容 `/copilot` 重定向） |
| 摘要收口与调度中心 | 已完成 | 通过 | 已新增 `SUPER_ADMIN` 角色、`/scheduler` 调度中心、后端 `/api/admin/scheduler/*` 接口、Celery Beat/Worker 统一任务调度；首页与病害页已移除重复摘要，摘要主页面为 `/ai-insights`；知识采集新增 `fetchStatus/lastError/successRate` 可观测字段 |
| AI建议入库 | 已完成 | 通过 | 已新增 `/api/ai-insights/recommendations` 生成与历史查询，以及 `/api/ai-insights/recommendations/confirm` 草稿确认入库；DeepSeek 不可用自动 fallback |
| 专家审批 | 已完成 | 通过 | 已新增 `/api/tasks/{id}/approve` 与 `/expert` 审批页；支持可选指派工人并完成 `PENDING -> APPROVED` |
| 工人执行 | 已完成 | 通过 | 已新增 `/api/tasks/{id}/claim|start|complete` 与 `/worker` 执行页；支持结构化完工回填并完成 `APPROVED -> IN_PROGRESS -> COMPLETED` |
| 时序策略 | 已完成 | 通过 | 已新增 15m/1d continuous aggregates、refresh/retention policy、应用/回滚/验收脚本；`/api/sensor/series` 已按范围自动切层（`<=24h raw`、`>24h 15m`、`>30d 1d`） |
| 可观测性 | 已完成 | 通过 | 已新增结构化日志、慢请求追踪、`/api/admin/observability/*` 与 `/observability` 超管页；`scripts/verify.sh observability` 可复现实控失败并校验链路一致性 |
| 联调回归 | 已完成 | 通过 | 已新增 `scripts/verify.sh regression` 回归矩阵总控、前端登录/RBAC E2E smoke 与后端 pytest；可一键执行 视觉推理-可观测性 全链路回归并输出报告 |
| 生产部署 | 已完成 | 通过（待云端外部依赖复验） | 已新增生产 Dockerfile、`docker-compose.prod.yml`、Nginx 网关、部署/验收脚本；本地代码级与脚本逻辑验收通过，待真实云端 `DATABASE_URL/REDIS_URL/对象存储` 参数复验 |

## 2. 建议排期（4 周）

1. 第 1 周：基础能力阶段（基础设施、鉴权、后端骨架）
2. 第 2 周：数据与视觉链路阶段（数据接入、视觉异步链路）
3. 第 3 周：智能建议与执行闭环阶段（Copilot、审批、工人端闭环）
4. 第 4 周：管理首页、稳定性与上线阶段（看板完善、策略、测试、部署）

## 3. 里程碑验收

1. 里程碑一（第 1 周末）：可登录、数据库连通、API 健康检查通过
2. 里程碑二（第 2 周末）：上传病害图后可异步返回识别结果
3. 里程碑三（第 3 周末）：AI 建议 -> 专家审批 -> 工人执行全流程跑通
4. 里程碑四（第 4 周末）：容器化部署完成，回归测试通过

当前状态：
- 里程碑一：已达成（基础能力阶段 已具备本地验收条件）
- 里程碑二：已达成（病害识别异步链路 上传后可实时看到任务状态完成）

## 3.1 数据接入与重试/传感器查询接口 时间约定

- Hoogendoorn Partner API 的 `Start` / `End` 使用 UTC 时间，并以无时区字符串发送。
- 返回体中的 `dateTime` 同样按 UTC 无时区字符串解释。
- 返回体中的 `utcOffset` 仅作为展示偏移元数据保留，不参与二次换算。
- 后端统一将 `sensor_data.recorded_at` 以 UTC 存储。
- 前端与报表层在展示阶段再转换到用户本地时区（当前默认中国时区 `+08:00`）。
- 对外 `sensor` 查询 API 与 Hoogendoorn 内部 provider 不同：对外 API 的 `start/end` 必须携带时区偏移或 `Z`，避免 UTC-naive 语义外泄到业务层。

## 3.2 传感器查询接口 验收备注

- `GET /api/sensor/raw` 已实测支持：
  - 显式 `start/end` 时间区间查询
  - `zone` 过滤
  - `metrics=temperature,humidity,ec,ph` 子集过滤
  - 无时区输入返回 `422`
  - `start > end` 返回 `422`
- `GET /api/sensor/series` 已实测支持：
  - `range=24h` 默认聚合
  - 自定义 `start/end`
  - `bucket=5m|15m|1h|6h|1d|auto`
  - 聚合结果同时返回 UTC 与本地时间
- `GET /api/sensor/dashboard` 已实测返回：
  - `summary`：`latest / avg / min / max / sampleCount`
  - `series`：四类指标时序点
  - `meta`：`range / bucket / timezone / storageTimezone`
- 空数据区间返回空 `summary` 和空序列，不返回 `500`
- `GET /api/sensor/*` 已切换内网令牌模式：支持 `X-API-Token`，生产环境未配置 `BACKEND_API_TOKEN` 时返回 `500`，避免公开裸露接口
- 回归通过：
  - `/health` 返回 `200`
  - `/integrations/hoogendoorn/status` 返回正常

## 3.3 管理首页 验收备注

- `/dashboard` 仍受 NextAuth 保护，未登录访问时会重定向到 `/login`
- 新增前端内部代理：
  - `GET /api/dashboard/sensor?range=24h|7d`
  - 由 Next.js route handler 代理到 FastAPI `GET /api/sensor/dashboard`
- 新增分区态势代理：
  - `GET /api/dashboard/zones?range=24h|7d`
  - 由 Next.js route handler 代理到 FastAPI `GET /api/sensor/raw` 并聚合为分区最新值
- Dashboard 首版已实现：
- 当前已重构为中文“智慧农业管理系统”壳子：
  - 左侧菜单：数据总览、温室监测、传感器数据、病害识别、智能建议、任务中心、专家审批、工人执行、用户与权限、系统设置
  - 4 张 summary 卡片：平均温度 / 平均湿度 / 平均 EC / 平均 pH
  - 4 张单指标时序图
  - 温室分区态势：当前按真实 Hoogendoorn 控制实例名称聚合与展示
  - `24h / 7d` 范围切换
  - `30 秒` 自动轮询
  - 页面恢复可见时立即补拉
  - 手动刷新按钮
- 当前首版范围固定为全场总览，不包含交互式 zone 筛选
- 前端展示统一优先使用后端返回的本地时间字段：
  - `latestAtLocal`
  - `bucketStartLocal`
- 当前温室/设备命名已按官方 Partner API 实例名称语义化展示：
  - `1号温室北区 / 南区 / 育苗区`
  - `2号温室北区 / 南区 / 采摘区 / 展示区`
  - `3号温室北区 / 南区`
  - `4号温室北区 / 南区`
  - `1-4号温室施肥机`
- 传感器查询默认按当前激活 provider 过滤，避免 `mock` 与 `partner_api` 混查
- 已实测：
  - `GET /api/dashboard/sensor?range=24h` 返回 `200`
  - `GET /api/dashboard/sensor?range=7d` 返回 `200`
  - `GET /api/dashboard/zones?range=24h` 返回 `200`
  - `/dashboard` 未登录时返回 `307 -> /login`
  - `/monitor` 未登录时返回 `307 -> /login`
  - `frontend` 执行 `npm run lint` 通过
  - `frontend` 执行 `npm run build` 通过

## 3.4 查漏补缺记录（2026-03-06）

- 修复 Dashboard 路由冲突：删除重复 `src/app/dashboard/page.tsx`，保留 `src/app/(system)/dashboard/page.tsx`。
- 修复 React hydration 告警：
  - `ProLayout` SSR/客户端 class 差异通过 hydration-safe 渲染规避。
  - `RangeToggle`（Antd Segmented）增加固定 `name`，避免 SSR/CSR 随机 radio name 不一致。
- 修复分区刷新告警：`/api/dashboard/zones` 代理的 raw 查询 `limit` 调整到后端允许上限（`20000`）。
- 修复“最近采样停留旧数据”问题：
  - 后端 raw 查询改为 `recorded_at DESC` 取最近样本。
  - 首页 stale 数据时自动触发一次 Hoogendoorn 同步后再刷新。
- 补充同步接口权限控制：
  - 后端 `/integrations/hoogendoorn/sync`、`/integrations/hoogendoorn/mock/failures` 支持 `X-Admin-Token` 校验；
  - 生产环境若未配置 `BACKEND_ADMIN_TOKEN` 将拒绝启动同步管理接口。
  - 前端内部代理 `/api/dashboard/sync` 增加角色限制（仅 `ADMIN/EXPERT`）并透传管理员令牌。
- 优化分区展示规则：
  - 分成“温室气候分区 / 水肥系统”两组展示。
  - 温室仅展示温度/湿度；水肥系统仅展示 EC/pH。
  - 分区顺序调整为：1号南北、2号南北、3号南北、4号南北、育苗区、采摘区、展示区。

## 3.5 视觉推理/异步识别队列 验收备注（2026-03-06）

- 后端新增视觉接口：
  - `POST /api/vision/tasks`
  - `GET /api/vision/tasks/{task_id}`
  - `GET /api/vision/tasks?limit=20`
  - `GET /api/vision/runtime`
- 后端安全约束：`/api/vision/*` 复用内网令牌校验，支持 `X-API-Token`。
- 存储策略已落地：
  - 开发环境默认本地存储（`/files/*` 可访问上传文件）
  - 生产环境默认对象存储，若未配置对象存储关键参数则启动报错
- 前端已新增内部代理：
  - `POST /api/vision/tasks`
  - `GET /api/vision/tasks`
  - `GET /api/vision/tasks/[taskId]`
  - `GET /api/vision/runtime`
- `/vision` 页面已从占位页升级为可用联调页：
  - 图片上传
  - 任务列表与状态标签
  - `PROCESSING` 任务每 3 秒轮询
  - 最近任务摘要与运行时状态展示
- 实测通过：
  - `GET /api/vision/runtime` 返回 `200`
  - 上传图片后 `POST /api/vision/tasks` 返回 `202`
  - 任务状态可转为 `DONE`，并返回 `engine/device` 及检测结果

## 3.6 结果实时回传/AI摘要 验收备注（2026-03-06）

- 结果实时回传（识别结果回传）已完成：
  - 后端新增 WebSocket：`WS /api/ws/vision/tasks`
  - 前端新增 WS 地址代理：`GET /api/vision/ws-url`
  - `/vision` 页面改为事件驱动增量更新，移除 3 秒高频轮询
  - Worker 在任务受理/完成时会推送：
    - `vision.task.accepted`
    - `vision.task.updated`
- 病害识别异步链路 联调脚本已新增：
  - `scripts/verify.sh vision`
  - 覆盖 `runtime -> submit(202) -> websocket accepted/updated -> final query` 全链路
- AI摘要（AI 智能解析）已完成：
  - 后端新增：`GET /api/ai-insights/summary?hours=24`（兼容旧 `/api/copilot/summary`）
  - 后端新增知识库接口：`GET /api/ai-insights/knowledge`、`GET /api/ai-insights/knowledge/meta`（兼容旧 `/api/copilot/*`）
  - 输出字段包括：
    - 指标极值（`min/max/avg/latest`）
    - 异常采样点与异常累计时长（分钟）
    - 病害类型计数与总事件数
    - 中文叙述摘要 `narrative`
  - 前端接入：
    - `/ai-insights` 页面为摘要主页面，包含“AI 智能解析可视化 + 本地知识库分类检索”
    - `/copilot` 及子路由保留兼容重定向一个迭代周期
    - `/dashboard` 与 `/vision` 已移除重复摘要，仅保留业务总览/识别任务
  - 知识库采集：
    - 已新增关键词驱动采集脚本 `scripts/ops.sh harvest-knowledge`
    - 采集结果保存到 `backend/data/knowledge_base.json`
    - 采集健康字段新增：`lastAttemptAt`、`fetchStatus`、`lastError`、`successRate`

## 3.7 摘要收口与调度中心 验收备注（2026-03-07）

- `SUPER_ADMIN` 角色已落地：
  - Prisma `UserRole` 增加 `SUPER_ADMIN`
  - seed 新增 `superadmin@example.local`
  - `/scheduler` 页面与调度 API 仅 `SUPER_ADMIN` 可访问
- 调度中心已落地：
  - 后端新增 `GET /api/admin/scheduler/jobs|runs|health`
  - 后端新增 `POST /api/admin/scheduler/jobs/{jobId}/run|pause|resume`
  - 前端新增 `/scheduler` 管理页面（任务清单、执行历史、手动执行、暂停/恢复）
- 调度引擎已统一：
  - Celery Worker + Celery Beat 纳管以下任务：
    1. Hoogendoorn 增量同步（5分钟）
    2. 知识库采集刷新（每天 03:30）
    3. Copilot 摘要预计算（15分钟）
    4. 视觉任务超时清理（2分钟）
- 采集增强已落地：
  - 支持 `public_html`、`rss`、`api_key_source`
  - 新增环境变量占位：`KB_HARVEST_ENABLED`、`KB_HARVEST_TIMEOUT_SECONDS`、`KB_SOURCE_*_API_KEY`、`KB_SOURCE_*_BASE_URL`
  - 明确不实现网页登录采集

## 3.8 AI建议入库 验收备注（2026-03-07）

- 后端新增 AI 智能解析建议接口：
  - `POST /api/ai-insights/recommendations`
  - `GET /api/ai-insights/recommendations?limit=20&status=PENDING`
  - `POST /api/ai-insights/recommendations/confirm`
- 建议入库策略：
  - 复用 `tasks` 表，不新增 schema/migration
  - 首次生成仅写入 `copilot_rt.recommendation_drafts`（`PENDING` 草稿）
  - 人工确认后写入 `tasks`（`source=AI`、`status=PENDING`）
  - `metadata.aiInsights` 持久化 `reason/suggestedRole/dueHours/llm/fallbackUsed/knowledgeRefs`
- 生成策略：
  - 优先调用 DeepSeek（`DEEPSEEK_API_KEY`）
  - API 异常、超时、解析失败时自动降级规则引擎 fallback，保证接口可用
- 前端接入：
  - `/ai-insights/recommendations` 页面新增“AI 建议草稿生成与确认入库”模块
  - 支持参数：`hours`、`zone`、`instruction`、`maxItems`
  - 支持查看草稿历史与确认后任务（含 `taskId`、状态、优先级、建议角色、来源标签）
- 新增验收脚本：
  - `scripts/verify.sh insights`
  - 验证链路：生成草稿 -> 草稿确认 -> 写入任务库 -> 历史查询 -> 断言 `source=AI` 且 `status=PENDING`

## 3.9 专家审批/工人执行 验收备注（2026-03-07）

- 后端任务域接口已落地：
  - `GET /api/tasks`
  - `GET /api/tasks/{taskId}`
  - `GET /api/tasks/assignees`
  - `POST /api/tasks/{taskId}/approve`
  - `POST /api/tasks/{taskId}/claim`
  - `POST /api/tasks/{taskId}/start`
  - `POST /api/tasks/{taskId}/complete`
- 状态机与权限已收口：
  - 审批仅管理角色可操作，且仅允许 `PENDING -> APPROVED`
  - 工人仅可操作本人任务，支持 `APPROVED -> IN_PROGRESS -> COMPLETED`
  - 并发接单使用条件更新，冲突返回 `409`
- 结构化完工回填已落地：
  - 固定字段（`operationType/executedActions/readingsBefore/readingsAfter/materials/anomalies/resultSummary/attachments`）
  - 持久化到 `tasks.metadata.executionReport`
- 前端页面已升级：
  - `/expert`：待审任务 + 一键审批（可选指派工人）
  - `/worker`：接单/开始/完工闭环与结构化回填弹窗
  - `/tasks`：管理视角任务追踪
- 新增验收脚本：
  - `scripts/verify.sh tasks`
  - 验证链路：创建待审任务 -> 审批 -> 接单 -> 开工 -> 完工 -> 回查结构化回填

## 3.10 冻结基线（2026-03-07）

- 基线校验脚本结果：
  - `scripts/verify.sh vision`：通过
  - `scripts/verify.sh scheduler`：通过
  - `scripts/verify.sh insights`：通过
  - `scripts/verify.sh tasks`：通过
- 安全收口：
  - `copilot` 与 `admin/scheduler` 接口已切换为“请求头 + DB 一致性”身份校验，不再仅信任 `X-User-Role`
  - `BACKEND_API_TOKEN` 统一改为受保护接口强制要求
- 冻结提交信息：
  - 冻结时间：2026-03-07 21:36（Asia/Shanghai）
  - 提交号：`8889ee6`
  - 冻结报告：`.devlogs/full-regression/20260307-213613/report.md`

## 3.11 时序策略 验收备注（2026-03-07）

- Timescale 策略已落地：
  - `backend/app/db/policies/timeseries_policies.sql`
  - 连续聚合视图：
    - `sensor_samples_15m`
    - `sensor_samples_1d`
  - 策略：
    - `policy_refresh_continuous_aggregate`（15m/1d）
    - `policy_retention`（`sensor_data`、`sensor_samples_15m`）
- 查询路由已落地：
  - `GET /api/sensor/series` 自动切层：
    - `<=24h`：raw hypertable
    - `>24h` 且 `<=30d`：15m cagg
    - `>30d`：1d cagg
  - `>30d` 非 `1d` bucket 请求会返回 `422`，避免误用细粒度查询拖慢历史报表。
- 新增脚本：
  - `scripts/ops.sh apply-timeseries-policy`
  - `scripts/ops.sh rollback-timeseries-policy`
  - `scripts/verify.sh timescale`
- 验证结果：
  - continuous aggregates = 2（`sensor_samples_15m/sensor_samples_1d`）
  - refresh policies >= 2
  - retention policies >= 1
  - `scripts/verify.sh timescale` 通过（含 `>30d -> bucket=1d` 与 422 guard 验证）

## 3.12 可观测性 验收备注（2026-03-07）

- 可观测性准备阶段（重启脚本稳定性小修）已完成：
  - `scripts/ops.sh restart-dev` 增加 backend `/health` 就绪探测与短退检测（启动后 1 秒二次存活校验）。
  - 新增 `wait_for_http_health`，避免“端口已开但服务未就绪”导致的误判。
- 后端可观测能力已落地：
  - 请求日志改为结构化 JSON 输出，统一字段：
    - `request_id/user_id/user_role/route/domain/latency_ms/status_code/error_code`
  - 慢请求阈值：
    - 新增 `SLOW_REQUEST_THRESHOLD_MS`（默认 `1000`）
    - 超阈值请求会打 `warning`，并写入 `observability_http_events`
  - 新增可观测接口（仅 `SUPER_ADMIN`）：
    - `GET /api/admin/observability/overview`
    - `GET /api/admin/observability/errors`
    - `GET /api/admin/observability/slow-requests`
    - `GET /api/admin/observability/task-failures`
  - Celery 失败聚合与调度中心对齐：
    - 失败来源基于 `scheduler_job_runs`
    - 可观测中心与调度中心可对账同一任务失败次数
- 前端可观测管理页已落地：
  - 新增 `/observability`（仅 `SUPER_ADMIN` 可见）
  - 新增菜单“可观测中心”
  - 页面展示：
    - 最近 24h 错误请求
    - 慢接口/慢请求排行
    - Celery 任务失败排行
- 新增验收脚本：
  - `scripts/verify.sh observability`
  - 验证链路：
    1. 人工制造一次 API 422 失败（`/api/sensor/raw?limit=50000`）
    2. 人工制造一次慢请求（`X-Debug-Sleep-MS:1300`）
    3. 注入一次受控调度失败 run
    4. 校验 observability 与 scheduler 失败统计一致
  - 当前结果：通过

## 3.13 联调回归 验收备注（2026-03-07）

- 新增统一回归总控脚本：
  - `scripts/verify.sh regression`
  - 串联校验：
    - `AUTH-UI`（前端登录/重定向/RBAC E2E smoke）
    - `BACKEND-UNIT`（pytest）
    - `BACKEND-COMPILE`
    - `FRONTEND-LINT`
    - `FRONTEND-BUILD`
    - `病害识别异步链路`、`摘要收口与调度中心`、`AI建议入库`、`审批与执行闭环`、`时序策略`、`可观测性`
  - 执行后输出矩阵报告到 `.devlogs/full-regression/<timestamp>/report.md`
- 新增前端 E2E smoke：
  - `frontend/tests/e2e_smoke.sh`
  - 覆盖：
    - 未登录访问 `/dashboard` 重定向
    - 专家登录后 `/dashboard` 与业务代理可访问
    - `SUPER_ADMIN` 可访问 `/scheduler`、`/observability`
    - `WORKER` 访问超管接口返回 `403`
- 新增后端单元测试：
  - `backend/tests/test_observability_utils.py`
  - `backend/tests/test_auth_context_validators.py`
- 运行结果（本次）：
  - `scripts/verify.sh regression`：通过（PASS=11，FAIL=0）
  - 报告路径示例：`.devlogs/full-regression/20260307-213613/report.md`

## 3.14 生产部署 验收备注（2026-03-07）

- 生产容器与编排已落地：
  - `backend/Dockerfile`
  - `frontend/Dockerfile`（Next.js standalone）
  - `docker-compose.prod.yml`
  - `docker/nginx/default.conf`
- 生产拓扑已锁定并实现：
  - 服务：`nginx + frontend + backend + celery-worker + celery-beat`
  - 外部依赖：`DATABASE_URL`、`REDIS_URL`（不内置 db/redis 容器）
  - 重启策略：`restart: unless-stopped`
- 网关路由已收口：
  - `/` -> `frontend`
  - `/api/ws/vision/tasks` -> `backend`（Upgrade/Connection 头透传）
  - `/backend-health` -> `backend /health`
  - 保留 Next.js 内部 `/api/*` 代理链路，不做全量 `/api/*` 直转后端
- 前端代理基址已升级为双地址策略：
  - `BACKEND_INTERNAL_BASE_URL`（Next route handlers -> backend）
  - `BACKEND_PUBLIC_BASE_URL`（浏览器 WS/公开入口地址）
  - 兼容回退：`API_BASE_URL` / `NEXT_PUBLIC_API_BASE_URL`
- 新增脚本：
  - `scripts/ops.sh check-production-env`（生产变量预检，部署前硬校验）
  - `scripts/ops.sh deploy-production`（一键 `up -d --build`）
  - `scripts/verify.sh production`（容器状态 + 网关 + `/backend-health` + Vision WS 路径探测）
- 新增上线 Runbook：
  - `docs/production-go-live-checklist.md`（参数矩阵、Go/No-Go 清单、回滚步骤）
- 本地 prod-like 验证（2026-03-07）：
  - `docker compose -f docker-compose.prod.yml build frontend backend`：通过
  - `bash scripts/verify.sh production`：通过
  - 校验点：`/`、`/backend-health`、`/api/ws/vision/tasks`（握手探测返回 400，路由可达）
- 说明：
  - 当前仓库已满足 生产部署 代码交付与可执行脚本要求。
  - 真实云端“一条命令拉起并健康通过”仍需填充外部 PG/Redis/对象存储生产参数后复验。

## 4. 每日执行看板模板（To Do / Doing / Done）

> 使用方式：每天复制以下模板为当天记录（例如 `docs/board-2026-03-03.md`）。
