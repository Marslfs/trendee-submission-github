# trendee-assessment ｜ 万悉科技 AI 数据工程师笔试

> **关于这个仓库**：这是「万悉科技 AI 数据工程师（NLP 方向）」笔试题的完整作答，两道题各自是一条可运行的数据管线，代码、SQL、Prompt、评测脚本、设计文档和提交历史都在这里。建议按 **`docs/方案书.pdf` → 各目录 README → `docs/design.md`** 的顺序看：前者 3 分钟能看清设计取舍，后者能看到实现细节。
>
> **不随仓库分发的内容**：① 题目 PDF 与品宣 PDF 属出题方材料，且体积较大（5.4MB），未入库——复现 Task 2 需自行放入 `data_raw/Trendee品宣-公开版.pdf`；② 真实 LLM 凭证不存在于仓库任何位置，仅保留 `.env.example` 键名模板，代码全部走 `os.getenv`，无 Key 时自动降级离线模式；③ 自评/评分类内部复盘文档未包含。
>
> **数据说明**：`data_raw/样例销售数据.xlsx` 为题目提供的示例数据；`task1_data_api/data/sales.duckdb` 为据此生成的预置库，保证 clone 后无需重跑摄取即可直接起 API。

两道题对应两条数据管线，均已完成并全量测试通过：

| 子项目 | 题目 | 一句话 | 测试 |
|---|---|---|---|
| [`task1_data_api/`](task1_data_api/) | 数据工程：销售数据 → 可高并发查询的销量 API | xlsx 脏数据 → DIM/DWD/DWS 三层数仓（DuckDB）→ FastAPI 趋势接口，幂等摄取 + 口径可解释 + 28 条对抗样本鲁棒性回归 | **56 passed** |
| [`task2_rag/`](task2_rag/) | AI 工程：品宣 PDF → RAG 品牌内容写作系统 | PDF → 带页码 chunk → BM25 检索（recall@5/MRR/nDCG 实测）→ `[S1..Sn]` 编号上下文 → LLM 生成 → 引用校验 → 资料不足拒答 | **17 passed** |

> 整体设计、技术取舍与实测结果汇总见 **`docs/方案书.pdf`**（3 分钟入口）；各任务的深度文档在各自目录内。
> 交付前按自检清单发现的 23 条问题及逐条处置见 **[`00 作业过程中的设计&测试 md文档/CHANGE_REPORT.md`](00%20作业过程中的设计&测试%20md文档/CHANGE_REPORT.md)**；方案书引用的提交 `bb4dc07` 可在 commits 页直接查看，离线快照见 `docs/git-history.txt`。

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

# 3) 全部测试（在项目根执行；pytest.ini 已配置 pythonpath / testpaths）
.venv\Scripts\python -B -m pytest -q
```

实测输出（项目根）：

```text
........................................................................   [ 82%]
...............                                                            [100%]
87 passed in 5.24s
```

> 基线 17（Task1）+ 11（Task2）全部保留；其余为历次修复新增的验证用例（Task1 56 = 23 + 33 条鲁棒性回归；Task2 17 + 14 条 T2-I 鲁棒性）。
> 两个子项目都有顶层包 `src`，根 `conftest.py` 合并命名空间解决同名冲突；
> 在 `task1_data_api/`、`task2_rag/` 各自目录内执行 `python -m pytest tests -q` 同样全绿（56 / 31 passed）。

## 核心设计主张（详见各 README 与方案书）

- **Task 1**：数仓分 DIM / DWD / DWS 三层、刻意不建 ADS（唯一消费方是 trend API，ADS 触发条件写明在 design.md §1.3）；时区双列口径 dt_utc/dt_local、聚合一律用 dt_local；row_hash 幂等去重（300→288）；TTL 缓存 + 无状态水平扩支撑高并发。
- **Task 2**：BM25 而非纯向量（品宣语料专有名词密集，稀疏匹配更稳、零模型下载），检索质量有量化（36 条标注，recall@5 0.698 / MRR@10 0.834 / nDCG@10 0.742，rerank 贡献 MRR +0.11）；chunk 以段落为最小单元带 page/section（引用溯源前提）；幻觉控制三层防线——生成前三态闸门（normal / degrade / refuse，覆盖度 0.40~0.60 降级并在文首声明）、Prompt 铁律、生成后句级引用校验；语料指纹检测索引与语料不一致，防止重建后引用静默指错页；无 API Key 自动降级离线模式，链路不断。

## 项目结构

```
task1_data_api/   销售数据 → DuckDB + FastAPI（README · docs/ · sql/ · src/ · tests/ · scripts/ · examples/）
task2_rag/        品宣 PDF → RAG 写作系统（README · docs/ · src/ · prompts/ · eval/ · scripts/ · app.py）
data_raw/         题目材料：样例销售数据.xlsx（+ 本地自备的笔试题/品宣 PDF，PDF 不入 git）
docs/             方案书.pdf（整体设计 + 取舍对照 + 实测汇总）、git-history.txt（提交历史快照）
00 作业过程中的设计&测试 md文档/
                  岗位分析、技术栈选型与架构、CHANGE_REPORT.md（交付前 23 条问题处置）
conftest.py       根级 pytest 配置（解决两个子项目顶层包 src 同名冲突）
pytest.ini        pythonpath / testpaths
.env.example      LLM_* 三项配置模板（真实 .env 不入 git）
```

## 实测数字速览

| 项 | 数字 |
|---|---|
| Task 1 摄取 | 300 行 → 12 条重复剔除 → 288 行落库，幂等重跑 inserted=0 |
| Task 1 打标 | core 12 / gray_zone 1 / excluded 17（商品维度）；DWS 预聚合 111 行；28 条题面外对抗样本 100% 通过、SQL/Python 零差异、打标冲突 0 |
| Task 1 API | 全链路毫秒级；TTL 缓存 60s 命中第二次 ~3ms |
| Task 2 解析 | PDF 36 页全解析 → 40 chunks 覆盖 36/36 页 |
| Task 2 检索 | 36 条人工标注：recall@5 0.698 / MRR@10 0.834 / nDCG@10 0.742（三档配置可复算） |
| Task 2 生成 | 2 篇真实文章引用覆盖率 6/6、0 编造、0 告警；1 个语料外主题被拒答 |
| 测试 | 87 用例全过（Task1 56 + Task2 31；基线 17+11 保留） |
