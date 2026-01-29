# Gemini Platform - 系统使用说明文档

## 📖 目录

- [项目简介](#项目简介)
- [快速开始](#快速开始)
- [核心功能](#核心功能)
- [详细使用指南](#详细使用指南)
- [API 协议说明](#api-协议说明)
- [工具和脚本](#工具和脚本)
- [常见问题](#常见问题)
- [技术架构](#技术架构)

---

## 项目简介

Gemini Platform 是一个功能完整的 **AI 批量抓取管理平台**，支持多平台 API 调用、批量任务执行、智能数据管理和导出。

### 主要特性

✅ **多协议支持** - 标准 OpenAI 协议和私有 HMAC 协议  
✅ **动态解析** - 灵活的 JSON 路径解析模板系统  
✅ **批量任务** - 后台批量处理，支持自动重试  
✅ **智能配置** - System Prompt 预设，支持时间变量注入  
✅ **数据中心** - 完整的数据浏览、搜索、导出功能  
✅ **接口探测** - 实时测试 API 连接并获取响应结构  
✅ **数据备份** - 完整的数据库备份和恢复工具  

---

## 快速开始

### 1. 环境要求

- Python 3.8+
- SQLite 3

### 2. 安装依赖

```bash
pip install fastapi uvicorn sqlalchemy requests jinja2 pandas openpyxl
```

### 3. 启动服务

```bash
python main.py
```

服务启动后访问：**http://localhost:8000**

### 4. 初始化数据库

首次启动会自动创建数据库文件：`data/gemini_platform.db`

---

## 核心功能

### 功能模块概览

| 模块 | 功能描述 | 页面路径 |
|------|----------|----------|
| **任务列表** | 创建和查看批量抓取任务 | `/` |
| **API 配置** | 管理 API 密钥、解析模板、系统预设 | `/api_config` |
| **数据中心** | 浏览、搜索、导出抓取结果 | `/data_center` |
| **结果详情** | 查看单个任务的完整结果 | `/results/{task_id}` |

---

## 详细使用指南

### 一、API 配置管理

#### 1. API 密钥管理

**功能说明：**
- 添加、编辑、删除不同平台的 API 配置
- 支持两种协议类型：
  - **标准 API**：使用 Bearer Token 认证
  - **私有 HMAC**：使用 HMAC-SHA1/SHA256 签名认证

**配置步骤：**

1. 进入 **API 配置** 页面
2. 点击 **"添加 API 配置"**
3. 填写配置信息：
   - **平台名称**：自定义名称（如：Gemini 官方、私有代理）
   - **API 地址**：完整的 API 端点 URL
   - **API Key**：认证密钥
   - **协议类型**：选择认证方式
   - **HMAC Secret**：仅私有协议需要（签名密钥）
4. 点击 **"测试连接"** 验证配置

#### 2. 解析模板管理

**功能说明：**
- 为不同 API 响应格式定义 JSON 解析规则
- 支持动态路径映射，提取标准字段

**默认模板：**

**OpenAI 标准格式：**
```json
{
  "title": "choices.0.message.content",
  "answer": "choices.0.message.content",
  "reasoning": null
}
```

**私有协议格式：**
```json
{
  "title": "answer.0.value",
  "answer": "answer.0.value",
  "reasoning": null
}
```

**创建步骤：**

1. 在 **解析模板** 标签页点击 **"添加模板"**
2. 使用 **接口探测实验室** 获取真实 JSON 结构
3. 根据响应格式配置字段映射：
   - `title`：提取标题/摘要的路径
   - `answer`：提取完整回答的路径
   - `reasoning`：提取推理过程（如果有）
4. 保存模板

**路径格式示例：**
- `choices.0.message.content` → 访问 `choices[0]['message']['content']`
- `answer.0.value` → 访问 `answer[0]['value']`

#### 3. 系统指令预设

**功能说明：**
- 管理 System Prompt 模板
- 支持动态变量注入（如 `{DATE}` 时间变量）

**常用预设示例：**

**Web 模拟器：**
```
你是一个专业的网页模拟器。请根据用户的需求生成对应的网页内容。
当前时间：{DATE}

请直接返回完整的 HTML 代码，不要包含任何额外解释。
```

**代码助手：**
```
你是一个专业的编程助手。请帮助用户解决编程问题。

当前时间：{DATE}

要求：
1. 提供清晰易懂的代码示例
2. 解释关键步骤
3. 给出最佳实践建议
```

**创建步骤：**

1. 在 **系统指令预设** 标签页点击 **"添加预设"**
2. 输入预设名称
3. 编写 System Prompt 内容（支持 `{DATE}` 变量）
4. 保存预设

---

### 二、批量任务执行

#### 1. 创建抓取任务

**步骤说明：**

1. 在 **任务列表** 页面点击 **"新建任务"**
2. 选择配置参数：
   - **API 配置**：选择已配置的 API
   - **解析模板**：选择对应的解析规则
   - **系统指令**：选择预设的 System Prompt
   - **模型**：选择 AI 模型（如 `gemini-2.5-pro-exp-03-25`）
   - **思考等级**：设置思考深度（`thinking_1` ~ `thinking_5`）
   - **是否启用搜索**：是否启用 Google Search 工具
   - **重试次数**：失败重试次数（默认 3 次）
3. 在文本框中输入多个 Prompt（每行一个）
4. 点击 **"开始抓取"**

**任务状态说明：**

| 状态 | 说明 |
|------|------|
| ⏳ 等待中 | 任务已创建，等待执行 |
| 🔄 抓取中 | 正在执行批量请求 |
| ✅ 已完成 | 所有请求成功完成 |
| ❌ 异常 | 部分或全部请求失败 |

#### 2. 查看任务结果

**方式一：** 在任务列表中点击任务的 **"查看数据"** 按钮

**方式二：** 点击任务的 **"查看详情"** 进入结果详情页

**结果信息包含：**
- Prompt 内容
- AI 回答（Markdown 格式化）
- Token 消耗统计
- 执行时间
- 原始 JSON 响应

---

### 三、数据中心

#### 1. 数据浏览

**功能说明：**
- 查看所有抓取结果
- 支持关键词搜索
- 支持按任务筛选
- 显示统计信息（总记录数、Token 消耗、平均成本）

#### 2. 搜索和筛选

**搜索功能：**
- 输入关键词在 Prompt 或回答内容中搜索
- 支持模糊匹配

**筛选功能：**
- 选择特定任务查看结果
- 支持多选批量操作

#### 3. 数据导出

**导出步骤：**

1. 使用搜索/筛选功能定位目标数据
2. 点击 **"导出数据"** 按钮
3. 自动下载 Excel 文件（包含所有筛选结果）

**导出字段：**
- 任务 ID
- Prompt
- AI 回答
- 创建时间
- Token 消耗
- 模型信息

#### 4. 批量删除

**操作步骤：**

1. 勾选需要删除的记录
2. 点击 **"批量删除"** 按钮
3. 确认删除操作

---

## API 协议说明

### 标准 OpenAI 协议

**适用场景：**
- Gemini 官方 API
- 兼容 OpenAI 格式的第三方 API

**认证方式：**
```
Authorization: Bearer {API_KEY}
```

**请求格式：**
```json
{
  "model": "gemini-2.5-pro-exp-03-25",
  "messages": [
    {
      "role": "system",
      "content": "System Prompt"
    },
    {
      "role": "user",
      "content": "User Prompt"
    }
  ],
  "thinking_config": {
    "thinking_budget": 3
  }
}
```

### 私有 HMAC 协议

**适用场景：**
- 自建代理服务
- 需要签名认证的私有 API

**认证方式：**
```
X-Signature: {HMAC签名}
X-Timestamp: {时间戳}
X-Api-Key: {API_KEY}
```

**签名算法（v2.03）：**
```python
def get_hmac_auth(api_key: str, secret: str, timestamp: str) -> str:
    message = f"{api_key}{timestamp}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha1
    ).hexdigest()
    return signature
```

**请求格式：**
```json
{
  "model": "gemini-2.5-pro-exp-03-25",
  "system": "System Prompt",
  "prompt": "User Prompt",
  "thinking_budget": 3
}
```

---

## 工具和脚本

### 1. 数据库迁移工具

**文件位置：** `migrate_tool.py`

**功能：**
- 导出所有表数据为 JSON 备份
- 从 JSON 备份恢复数据

**使用方法：**

**导出数据：**
```bash
python migrate_tool.py export
```
导出文件：`data/backup_YYYYMMDD_HHMMSS.json`

**导入数据：**
```bash
python migrate_tool.py import data/backup_YYYYMMDD_HHMMSS.json
```

### 2. 数据库测试工具

**文件位置：** `test_db.py`

**功能：**
- 测试数据库连接
- 验证表关系映射
- 初始化测试数据

**使用方法：**
```bash
python test_db.py
```

---

## 常见问题

### Q1: API 连接失败怎么办？

**排查步骤：**

1. 检查 API 地址是否正确
2. 确认 API Key 有效
3. 如果是私有协议，检查 HMAC Secret 配置
4. 使用 **接口探测实验室** 测试连接
5. 查看服务器日志获取详细错误信息

### Q2: 解析模板配置错误导致数据为空？

**解决方法：**

1. 使用 **接口探测实验室** 获取真实 JSON 结构
2. 对照 JSON 结构调整路径配置
3. 路径格式：`数组索引使用数字，对象属性使用名称`
4. 示例：
   ```
   假设 JSON: {"data": {"items": [{"text": "hello"}, {"text": "world"}]}}
   提取第一条: data.items.0.text
   ```

### Q3: 批量任务执行缓慢？

**优化建议：**

1. 减少单批次的 Prompt 数量
2. 增加重试超时时间（在代码中调整）
3. 使用更快的 API 端点
4. 检查网络连接质量

### Q4: 数据库文件在哪里？

**位置：** `data/gemini_platform.db`

**备份建议：**
- 定期使用 `migrate_tool.py` 导出备份
- 备份文件存放在 `data/` 目录

### Q5: 如何导出所有数据？

**步骤：**

1. 进入 **数据中心** 页面
2. 不使用任何搜索/筛选条件
3. 点击 **"导出数据"** 按钮
4. 或使用迁移工具导出 JSON 备份

### Q6: System Prompt 中的 {DATE} 变量不生效？

**说明：**
`{DATE}` 变量仅在执行任务时自动替换，不会在预览时显示。实际请求中会自动注入当前时间。

---

## 技术架构

### 技术栈

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| **后端框架** | FastAPI | 高性能异步 Web 框架 |
| **数据库** | SQLite + SQLAlchemy ORM | 轻量级数据库 |
| **前端框架** | Bootstrap 5 + Jinja2 | 响应式 UI |
| **Markdown** | Marked.js | Markdown 渲染 |
| **代码高亮** | Highlight.js | 语法高亮 |
| **数据导出** | Pandas + openpyxl | Excel 导出 |
| **HTTP 客户端** | Requests | API 请求 |

### 项目结构

```
gemini_platform/
├── main.py              # 主应用程序 (FastAPI 路由)
├── database.py          # 数据库模型定义
├── auth_utils.py        # HMAC 认证工具
├── parser_utils.py      # JSON 路径解析工具
├── migrate_tool.py      # 数据库迁移工具
├── test_db.py           # 数据库测试工具
│
├── services/
│   ├── scraper.py       # 核心抓取逻辑
│   └── task_manager.py  # 批量任务调度
│
├── templates/           # HTML 模板
│   ├── base.html        # 基础模板
│   ├── index.html       # 任务列表
│   ├── api_config.html  # API 配置
│   ├── data_center.html # 数据中心
│   └── results.html     # 结果详情
│
└── data/
    └── gemini_platform.db # SQLite 数据库
```

### 数据库模型

| 表名 | 说明 |
|------|------|
| `api_config` | API 配置表 |
| `response_template` | 响应解析模板表 |
| `scrape_task` | 抓取任务主表 |
| `task_entry` | 结果详情表 |
| `task_preset` | 任务预设表 |

### 核心流程

**任务执行流程：**

```
1. 用户创建任务
   ↓
2. 创建 ScrapeTask 记录
   ↓
3. 启动后台任务
   ↓
4. 对每个 Prompt 执行：
   - 应用 System Prompt 预设
   - 调用 API（带重试）
   - 解析响应
   - 保存 TaskEntry
   ↓
5. 更新任务状态
   ↓
6. 完成任务
```

---

## 附录

### 端口配置

默认端口：**8000**

修改端口（编辑 `main.py`）：
```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 日志查看

服务日志输出到控制台，包含：
- API 请求日志
- 任务执行状态
- 错误和异常信息

### 开发模式

启用自动重载：
```bash
uvicorn main:app --reload
```

---

## 更新日志

### v1.0.0

✅ 首次发布
- 支持多平台 API 管理
- 批量任务执行
- 动态 JSON 解析
- 数据中心和导出
- 接口探测实验室

---

## 联系与支持

如有问题或建议，请提交 Issue 或联系开发团队。

---

**Gemini Platform** - 让 AI 批量抓取更简单高效！
