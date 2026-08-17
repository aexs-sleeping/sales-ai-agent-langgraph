# 产品需求文档（PRD）—— 虚拟销售客服助手 · 前后端分离改造

> 版本：1.0（2026-08-16） · 状态：待评审
> 本文档是 **FastAPI 后端** 与 **Vue3 前端** 并行开发的唯一契约，两端各自按本文档实现，互不依赖。

---

## 1. 项目概述

### 1.1 背景
现有系统是一个 Streamlit 单体应用（`backend/main.py` 直接调用 LangGraph 智能体），界面与后端耦合在同一 Python 进程中。本改造将其拆分为 **FastAPI 后端（API 服务）+ Vue 3 前端（电商客服界面）** 的前后端分离架构，智能体核心逻辑（LangGraph + Gemini + MySQL 数据层）保持不变并复用。

### 1.2 目标
- 提供标准的 REST + SSE 接口，供任意前端消费
- 实现电商客服风格的聊天界面：商品展示、下单、订单跟踪、个性化推荐、人工审批（HITL）
- 为后续扩展预留空间：多 LLM 供应商、支付（支付宝/微信）、多会话持久化

### 1.3 非目标（本次不做）
- 支付功能、用户认证/登录、多租户
- 会话持久化到数据库（MVP 用内存态）
- 多 LLM 供应商切换（后续单独迭代）
- 下线 Streamlit 版本（Vue 前端就绪并验收后再说）

### 1.4 用户与场景
| 用户 | 场景 |
|---|---|
| 普通顾客 | 咨询商品、搜索/浏览、下单、查订单、获取推荐 |
| 客服运营（演示） | 体验人机协同审批：敏感操作（下单）需人工批准/驳回 |

---

## 2. 前端功能需求（Vue 3 实现）

### 2.1 聊天主界面
- **F1 消息列表**：用户消息靠右、客服消息靠左的气泡式对话列表；自动滚动到底部
- **F2 输入与发送**：底部输入框 + 发送按钮；Enter 发送、Shift+Enter 换行；发送中禁用
- **F3 流式渲染**：客服回复以打字机效果逐字显示（消费 SSE `message` 事件）
- **F4 工具状态提示**：智能体调用工具时显示过程提示条（如"🔍 正在搜索商品…"、"📦 正在创建订单…"），对应 SSE `tool_status` 事件
- **F5 结构化渲染**：商品信息、价格、订单明细以卡片/列表结构化展示，不堆纯文本
- **F6 空状态**：无消息时展示欢迎引导页（客服形象 + 可尝试的提问示例）

### 2.2 商品与订单展示
- **F7 商品卡片**：搜索结果以卡片呈现——名称、分类、价格、库存、描述；卡片可点击触发快捷追问（如"帮我看看 X"）
- **F8 推荐商品**：推荐结果以商品卡片展示，并标注"为您推荐"
- **F9 订单卡片**：订单信息以卡片展示——订单号、日期、状态、商品明细（名称 x数量）、总金额；状态用标签/颜色区分（Pending/Shipped/Cancelled/Completed）

### 2.3 人工审批（HITL）
- **F10 审批卡片**：收到 `approval_required` 事件后，在对话流中渲染审批卡片——展示"AI 想执行的操作"、工具名、参数 JSON 详情
- **F11 批准/驳回**：卡片上提供「批准」「驳回」两个按钮；驳回时弹出原因输入框
- **F12 结果回写**：审批后继续渲染后续回复（消费 approve/deny 的 SSE 流），并明确展示"已批准 / 已驳回"反馈

### 2.4 会话管理
- **F13 新建会话**：侧边栏/顶部提供「新建会话」；新会话调用 `POST /api/conversations`，获得新的 `conversation_id`
- **F14 会话列表**（MVP 可简化）：侧边栏列出历史会话，可切换；MVP 允许只支持当前会话 + 新建
- **F15 侧边栏信息**：客服形象/名称、在线状态、功能简介（可购物/下单/查单）、清空会话

### 2.5 视觉风格（电商客服）
- **F16** 清晰明了的电商客服风格：品牌主色（推荐蓝 `#1E6FFF` 或电商橙）+ 清爽留白；居中聊天窗、两侧留白；中文界面；响应式（桌面优先，窄屏可用）
- **F17** 统一使用 Element Plus 组件（按钮/卡片/标签/对话框/加载态），避免混用自定义样式

---

## 3. 后端需求（FastAPI 实现）

### 3.1 服务职责
- 复用现有 `backend/agent/`（graph.py / tools.py / utils.py）与 `backend/database/`（MySQL / SQLAlchemy），**不改动智能体核心逻辑**
- 新增 `backend/api/` 层：路由、请求/响应模型、SSE 流式生成器
- 会话状态使用现有 `MemorySaver`（单进程内存态），以 `thread_id` 键
- 保留 `backend/main.py`（Streamlit）作为过渡期兜底，不删除

### 3.2 REST 端点
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回 `{status: "ok"}` |
| POST | `/api/conversations` | 新建会话，返回 `{conversation_id}`（uuid4，即 graph 的 thread_id） |
| GET | `/api/conversations` | 会话列表（内存态，MVP 返回基本元信息） |
| POST | `/api/chat` | 发送消息，SSE 流式返回（见 3.3） |
| POST | `/api/conversations/{id}/approve` | 批准待审批工具调用，SSE 流式返回续跑结果 |
| POST | `/api/conversations/{id}/deny` | 驳回（body 带 `reason`），SSE 流式返回续跑结果 |

**请求/响应模型（pydantic）：**
- `POST /api/chat` body：`{ "conversation_id": string, "message": string, "customer_id": string? }`
  - `conversation_id` 必填；`customer_id` 缺省用 `123456789`（沿用现有硬编码，未来可改为多客户）
- `POST /api/conversations/{id}/deny` body：`{ "reason": string }`
- 非 SSE 响应统一 `{ "status": "ok" | "error", ... }`；异常返回 HTTP 4xx/5xx + `{ "detail": "..." }`

### 3.3 SSE 事件协议（前后端契约核心）

**传输**：`Content-Type: text/event-stream`；事件格式 `event: <type>\ndata: <json>\n\n`。

| 事件类型 | data 载荷 | 说明 |
|---|---|---|
| `message` | `{ "content": string }` | AI 回复 token 增量（前端累积拼接） |
| `tool_status` | `{ "name": string, "status": "running"\|"success"\|"error", "args": object?, "result": object? }` | 工具调用生命周期提示；`result` 仅 success 携带（工具结构化输出的 JSON），前端据此渲染商品/订单卡片 |
| `approval_required` | `{ "tool_call": { "id": string, "name": string, "args": object } }` | 需要人工审批（仅下单 `create_order`） |
| `done` | `{}` | 本次流结束（正常） |
| `error` | `{ "message": string }` | 本次流失败 |

**生命周期约定：**
1. 前端 `POST /api/chat` → 后端运行 `graph.stream(..., stream_mode="messages")`：
   - 产生 AI token → 发 `message` 事件
   - 检测到工具调用 → 发 `tool_status(running)`；工具执行后 `tool_status(success|error)`
   - 若为敏感工具（`create_order`），执行流会在 `interrupt_before` 处停下 → 后端通过 `graph.get_state(config)` 检测 `snapshot.next` 非空 → 发 `approval_required`（含 pending tool_call 的 id/name/args）→ 发 `done`
2. 用户点击批准 → 前端 `POST /api/conversations/{id}/approve` → 后端 `graph.invoke(None, config)` 续跑，同样以 SSE 流式返回（复用同一事件协议）
3. 用户点击驳回 → 前端 `POST /api/conversations/{id}/deny` body `{reason}` → 后端用 `ToolMessage`（`tool_call_id` 匹配 pending 调用、content 说明驳回原因）`graph.invoke(..., config)` 续跑，SSE 流式返回

### 3.4 后端实现要点
- **入口**：新增 `backend/main_fastapi.py`，`uvicorn` 启动（端口默认 `8000`，可用 env 覆盖）
- **CORS**：允许 `http://localhost:5173`、`http://localhost:5174`（Vite dev server），`allow_methods=["*"]`，`allow_headers=["*"]`
- **SSE**：用 FastAPI `StreamingResponse`（`media_type="text/event-stream"`）+ 生成器；`message` 事件用 `stream_mode="messages"` 的 `(chunk, metadata)` 元组取 token 文本
- **会话表**：内存 dict `conversation_id -> {thread_id, customer_id, created_at, title?}`（`conversation_id` 即 thread_id）
- **配置**：`.env` 现有约定（MYSQL_*/GOOGLE_*/LangSmith），凭据零硬编码
- **日志**：结构化日志（请求/SSE 事件/错误），复用 `database.db_manager` 的 logging 风格

---

## 4. 数据与状态管理

| 状态 | 存储 | 说明 |
|---|---|---|
| 智能体对话状态 | `MemorySaver`（进程内） | key = thread_id；重启丢失（MVP 接受） |
| 会话元信息 | 后端内存 dict | conversation_id / customer_id / created_at |
| 商品/订单/客户数据 | MySQL（复用现有 `backend/database/`） | 读写仍走 tools → DatabaseManager |

> 后续（不在本期）：会话持久化到 MySQL、用户账户体系。

---

## 5. 非功能需求

- **可配置**：数据库/LLM/服务端口全部走 `.env`，敏感信息不硬编码、不进 git（`*.env` 已被 ignore）
- **错误处理**：后端任何异常转为 `error` SSE 事件或结构化 JSON；前端对 `error` 事件给出友好提示
- **性能**：聊天采用流式，首 token 尽快返回；不做重负载优化
- **可维护性**：前端组件按职责拆分（chat / products / orders / approval / conversations）；后端路由按模块拆分（chat / conversations）
- **兼容性**：保留 Streamlit 版可用（过渡期）

---

## 6. 技术选型

| 端 | 技术 | 版本 |
|---|---|---|
| 后端 | Python / FastAPI / uvicorn | 3.12 / 最新稳定 |
| 后端复用 | langgraph / langchain-core / langchain-google-vertexai / SQLAlchemy / pymysql | 现有锁定版本 |
| 前端 | Vue 3 / Vite / TypeScript | 3.5+ / 6.x |
| 前端 | Pinia / Element Plus / @microsoft/fetch-event-source | 最新稳定 |
| 前端 | HTTP | 原生 fetch 或 axios（SSE 用 fetch-event-source） |

> 说明：`@microsoft/fetch-event-source` 用于 **POST + SSE**（原生 `EventSource` 仅支持 GET）；`/api/chat`、approve、deny 均为 POST + SSE。

---

## 7. 里程碑与 git 分支计划

| 里程碑 | 内容 | 分支 | 状态 |
|---|---|---|---|
| M0 | 数据层迁移 MySQL | `feature/database-mysql` | ✅ 已合并 dev |
| M1 | 本文档（PRD） | `feature/product-prd` | 🔄 本次 |
| M2 | FastAPI 后端（REST + SSE + HITL 端点） | `feature/backend-fastapi` | 待开发（独立 worktree 子代理） |
| M3 | Vue 3 前端（聊天/商品/订单/审批/会话） | `feature/frontend-vue3` | 待开发（独立 worktree 子代理） |
| M4 | 联调验收（curl + 浏览器 E2E） | dev | 待办 |

**git 约定（延续既有规则）：** 每功能分支恰好 1 个提交；推送后**等用户审查**，获批后 `--no-ff` 合并到 `dev`；**未经用户要求禁止创建 PR**；`main` 保持稳定不动。
