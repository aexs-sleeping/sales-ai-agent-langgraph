# 智购客服前端（Vue 3）

虚拟销售客服助手的 Vue 3 + TypeScript 前端，消费 FastAPI 后端的 REST + SSE 接口
（契约见 `docs/PRD.md` §2 与 §3.3）。

## 技术栈

- Vue 3.5 / Vite 6 / TypeScript
- Pinia（状态管理）
- Element Plus（UI 组件，品牌色 `#1E6FFF`）
- @microsoft/fetch-event-source（POST + SSE）

## 开发

```bash
npm install
npm run dev      # http://localhost:5173，/api 代理到 http://localhost:8000
npm run build    # vue-tsc 类型检查 + 生产构建
```

## 目录结构

```
src/
  api/        REST 客户端 + SSE 封装（chat / approve / deny 共用）
  stores/     Pinia chat store（消息、conversation_id、审批、流式状态）
  types/      领域类型与 SSE 事件类型
  utils/      金额/日期格式化、结构化数据（商品/订单）提取
  components/
    chat/     ChatView、ChatMessage、MessageInput、ToolStatusBar、WelcomeEmpty
    products/ ProductCard（含"为您推荐"标注）
    orders/   OrderCard
    approval/ ApprovalCard（审批卡片 + 驳回原因对话框）
    layout/   ChatSidebar
```

## SSE 事件处理

- `message`：AI token 增量，累加渲染，流式打字机
- `tool_status`：工具调用生命周期提示条（running/success/error）
- `approval_required`：渲染审批卡片（工具名 + 参数 JSON），批准/驳回
- `done`：结束当前流
- `error`：友好错误提示

## 说明

- 后端工具结果不随 SSE 契约传输，前端从 AI 回复中的 JSON 片段
  （```json 代码块 / 顶层对象）以及 `tool_status(success)` 可选 `result` 字段
  提取结构化数据渲染商品/订单卡片；提取不到时退化为纯文本。
- `conversation_id` 即 LangGraph 的 `thread_id`；`customer_id` 缺省由后端
  回退到 `123456789`（PRD §3.2）。
