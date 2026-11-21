# trendee-assessment ｜ 万悉科技 AI 数据工程师笔试

两道题对应两条数据管线，均已完成并全量测试通过：

| 子项目 | 题目 | 一句话 | 测试 |
|---|---|---|---|
| [`task1_data_api/`](task1_data_api/) | 数据工程：销售数据 → 可高并发查询的销量 API | xlsx 脏数据 → DIM/DWD/DWS 三层数仓（DuckDB）→ FastAPI 趋势接口，幂等摄取 + 口径可解释 | **17 passed** |
| [`task2_rag/`](task2_rag/) | AI 工程：品宣 PDF → RAG 品牌内容写作系统 | PDF → 带页码 chunk → BM25 检索 → `[S1..Sn]` 编号上下文 → LLM 生成 → 引用校验 → 资料不足拒答 | **11 passed** |

> 整体设计、技术取舍与实测结果汇总见 **`docs/方案书.pdf`**（评审 3 分钟入口）；各任务的深度文档在各自目录内。

## 快速开始

```bash
# 0) 环境（一次性）
python -m venv .venv
.venv\Scripts\activate               # PowerShell 用 Activate.ps1（需先 Set-ExecutionPolicy -Scope Process Bypass）
pip install -r requirements.txt
copy .env.example .env               # LLM_API_KEY / LLM_BASE_URL / LLM_MODEL（Task 2 生成环节用；不配则离线模式）

# 1) Task 1：摄取 + API
cd task1_data_api
python -m src.ingest                 # xlsx → DuckDB，幂等可重跑
uvicorn src.api:app --reload         # http://127.0.0.1:8000/docs 是 Swagger UI

# 2) Task 2：构建索引 + 生成
cd ../task2_rag
python -m src.parse && python -m src.clean && python -m src.chunk && python -m src.index
python -m pipeline "为什么中国出海品牌需要进行 GEO 优化"     # CLI 全链路
streamlit run app.py                                          # 或 Demo 页面

# 3) 全部测试
cd .. && .venv\Scripts\python -m pytest task1_data_api/tests task2_rag/tests -q
```

## 核心设计主张（详见各 README 与方案书）

- **Task 1**：数仓分 DIM / DWD / DWS 三层、刻意不建 ADS（唯一消费方是 trend API，ADS 触发条件写明在 design.md §1.3）；时区双列口径 dt_utc/dt_local、聚合一律用 dt_local；row_hash 幂等去重（300→288）；TTL 缓存 + 无状态水平扩支撑高并发。
- **Task 2**：BM25 而非纯向量（品宣语料专有名词密集，稀疏匹配更稳、零模型下载）；chunk 以段落为最小单元带 page/section（引用溯源前提）；幻觉控制三层防线——生成前双闸门拒答、Prompt 铁律、生成后句级引用校验；无 API Key 自动降级离线模式，链路不断。

## 项目结构

```
task1_data_api/   销售数据 → DuckDB + FastAPI（README · docs/ · sql/ · src/ · tests/ · examples/）
task2_rag/        品宣 PDF → RAG 写作系统（README · docs/eval.md · src/ · prompts/ · eval/ · app.py）
data_raw/         三份原始材料（笔试题 PDF / 样例销售数据 xlsx / 品宣 PDF 36 页）
docs/             方案书.pdf（整体设计 + 取舍对照 + 实测汇总）
.env.example      LLM_* 三项配置模板（真实 .env 不入 git）
```

## 实测数字速览

| 项 | 数字 |
|---|---|
| Task 1 摄取 | 300 行 → 12 条重复剔除 → 288 行落库，幂等重跑 inserted=0 |
| Task 1 打标 | core 12 / gray_zone 1 / excluded 17（商品维度）；DWS 预聚合 111 行 |
| Task 1 API | 全链路毫秒级；TTL 缓存 60s 命中第二次 ~3ms |
| Task 2 解析 | PDF 36 页全解析 → 40 chunks 覆盖 36/36 页 |
| Task 2 生成 | 2 篇真实文章引用覆盖率 6/6、0 编造、0 告警；1 个语料外主题被拒答 |
| 测试 | 28 用例全过（17 + 11） |
