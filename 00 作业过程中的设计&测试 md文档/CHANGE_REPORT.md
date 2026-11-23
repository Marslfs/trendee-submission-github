# 交付前自检与修复记录（CHANGE_REPORT）

> 对象：`trendee-assessment` 源工程及其派生交付包
> 方式：交卷前按评分维度自查，把发现的问题逐条修掉并留下可复现证据；解释器统一 `.venv\Scripts\python.exe`，测试一律 `-B` + `PYTHONDONTWRITEBYTECODE=1`
> 两轮：第一轮 23 项（A 级硬伤 6 / B 级文档-代码对齐 11 / C 级增强 6），第二轮按 v1.1 评分标准的鲁棒性与量化维度补强 8 项

## 一、第一轮：23 项逐条处置

| ID | 改了什么 | 涉及文件 | 验证命令 | 验证结果 |
|---|---|---|---|---|
| A1 | 方案书 §2.4 用 `b.code()`(Consolas/无 CJK 字形) 渲染中文导致整页豆腐块；改普通段落 + SimHei，5 条铁律从 `system.md` 逐字提取 | `docs/.book/engine.py`、`docs/.book/build.py`、`docs/方案书.pdf` | `python -B docs/.book/build.py` + pymupdf 抽全文 | 页内 `\ufffd`/`□` 均 0；铁律与 system.md 逐字一致（折行不影响文字） |
| A2 | 根命令报 `No module named 'src'`；新增 `pytest.ini` + 根 `conftest.py` 合并两个同名 `src` 命名空间包；README 改真实命令并贴输出 | `pytest.ini`、`conftest.py`、`README.md` | `.venv\Scripts\python -B -m pytest -q` | 根 **87 passed**；子目录 **56 / 31 passed**（基线 17+11 全保留） |
| A3 | `rerank.py` 中 `str < int` 必抛 TypeError 被 `except Exception: return None` 静默吞；改先转 int 再比较、异常收窄、降级全部 `logger.warning`、开放 `get_client()` 可替换 hook | `task2_rag/src/rerank.py`、`tests/test_rerank_llm.py` | `pytest tests/test_rerank_llm.py -q` | 3 例假 client 用例通过；`mode="llm"` 按模型顺序返回、乱码降级、越界编号丢弃均有日志 |
| A4 | Q1 外层 `WHERE tag_status='core'` 使 `gray_zone_sales` 恒 0；改单次扫描双 CASE 聚合，并去掉默认 website 过滤（gray_zone 只在 app 出现） | `task1_data_api/sql/04_queries.sql`、`docs/checklist.md` | 真实库重跑 Q1 | 67 行；前三行 `4,1,0 / 25,2,0 / 13,1,10`；1-23 = `3,1,9`；**11 天非零、最大 17** |
| A5 | 方案书虚构 `dim_product.tag_rule` 与 `skirt/length` 排斥词；按"真做出来"修：词级规则、schema 加列、SQL/Python/API/维表四端一致 | `sql/01_dwd_schema.sql`、`02_dwd_tag.sql`、`src/normalize.py`、`src/ingest.py`、`src/api.py`、`docs/.book/build.py`、`docs/mapping.xlsx`、`examples/products-core.json`、`tests/test_tag_rule.py` | `GET /api/v1/products?tag=excluded`；`pytest tests/test_tag_rule.py -q` | 2027 `R2`、2017 `R4`；`R1:4/R2:1/R3:12/R4:1/R5:12`；SQL 与 Python **30 商品逐商品一致**；core12/gray1/excluded17 不变 |
| A6 | 提交包无 `.git` 无法佐证 `bb4dc07`；查明该 hash 在源工程 `git log` **真实存在**（时区 bug 修复），生成随包历史快照并在方案书注明查阅路径 | `docs/git-history.txt`、`docs/.book/build.py`、`.gitignore` | `git log --oneline \| grep bb4dc07` | 命中 `bb4dc07 fix(task1): tz-aware binding...` |
| B1 | 方案书 §1.2 `row_hash` 8 字段 → 7 字段并列出全部字段名 | `docs/.book/build.py`、`docs/mapping.xlsx` | 全库 grep `8 字段` | 0 处 |
| B2 | 方案书 §1.7 的 5 条规则名 → 代码真名（现 6 条，见第二轮 R7） | `docs/.book/build.py`、`docs/dq_report.md` | 全库 grep 旧规则名 | 0 处 |
| B3 | `17 领域词` → 23（含 GEO/LLM/Trendee/JSON-LD） | `docs/.book/build.py`、`task2_rag/README.md` | 运行时读 `index.DOMAIN_WORDS` | **23 个**；grep `17 领域词` 0 处 |
| B4 | `LIKE '%maxi%'` 子串匹配 → 词级匹配，与 Python 词集判定对齐 | `sql/02_dwd_tag.sql`、`tests/test_tag_rule.py` | `pytest tests/test_tag_rule.py -q` | 30 商品 SQL/Python 完全一致；`dress` 不再误匹配 `address` |
| B5 | guard.py 注释"外主题 < 0.2"与实测相反；改为真实数字并点明单靠分数闸门拦不住 | `task2_rag/src/guard.py` | 读源码注释 | 现为 0.653 / 0.750 / 0.550 / 0.641 实测值 |
| B6 | guard.py docstring 漏掉覆盖率闸门；重写为四层顺序 + 各自阈值 | `task2_rag/src/guard.py` | 读文件头 docstring | 现写明「无命中 → 分数 0.35 → 覆盖率 0.40/0.60 → 来源数 2」四层 |
| B7 | `dq_report.md` "五字段全同" → 6 字段全同（与所列 6 个字段名一致） | `task1_data_api/docs/dq_report.md`、`docs/mapping.xlsx` | 全库 grep `五字段` | 0 处 |
| B8 | `timeliness_coverage` 的 `passed` 硬编码 `True`（永真假检查）→ 真判声明区间覆盖，且降级为 `info`/不参与门禁 | `task1_data_api/src/ingest.py`、`docs/dq_report.md`、`docs/.book/build.py` | 查 `dq_report` 最新批次 detail | `covered=True`；detail 明写 `info 级别，不参与 error/warn 门禁` |
| B9 | `user.md` 首句写死 "Blog"；拆 4 个 genre 模板 + `pipeline.run()` 按 genre 路由，`user.md` 参数化为 `{genre}` | `prompts/user*.md`、`pipeline.py` | `pytest -q` | FAQ 模板明确"资料未覆盖则不回答" |
| B10 | 注释引用 `02_tag.sql` / `03_agg.sql` / `dq_checks` 等过期名 | `src/normalize.py`、`src/ingest.py`、`task1_data_api/README.md` | 全库 grep | 0 处 |
| B11 | 删除 GBK 乱码草稿 `_sec_guard_degrade.xml`；README 新增「附：四张原理图」正式引用 4 张卡 | `task2_rag/README.md`、`docs/cards/*` | `ls docs/cards/` | xml 已删；4 张 PNG + 4 个 `make_*.py` 全部被 README 引用 |
| C1 | 两态 guard 误拒 2/9 → 三态 `normal/degrade/refuse`；degrade 文首插覆盖度声明 + `app.py` `st.warning`；混淆矩阵与阈值扫描写进 eval.md | `guard.py`、`pipeline.py`、`app.py`、`docs/eval.md`、`scripts/scan_guard.py`、`tests/test_guard_tristate.py`、两张卡片 PNG | `python -B scripts/scan_guard.py` | **14 主题，误拒 0 / 误放 0，判对 14/14**；拒答样例仍 `refuse` |
| C2 | `perf.md` 只有推演无实测；新增 `bench.py`（30 万/300 万行、P50/P95、`EXPLAIN ANALYZE`）并重写 perf.md | `scripts/bench.py`、`docs/perf.md`、`docs/bench_result.md` | `python -B scripts/bench.py` | 明细 GROUP BY 1.7 → 8.2 ms；DWS 直查 1.4–2.3 ms；EXPLAIN 明细扫 2,999,808 行 / DWS 111 行 |
| C3 | 4 条核心 SQL 无窗口函数；新增 Q5 `LAG()` + 7 日滚动 | `sql/04_queries.sql`、`docs/design.md`、`docs/checklist.md`、README | 真实库跑 Q5 | 66 行；前三行 `4,NULL,4 / 25,4,29 / 13,25,42` |
| C4 | 趋势接口无数据日不返回行；新增 `fill_missing_dates`，默认 false 保持旧快照 | `src/api.py`、`examples/`、`tests/test_fill_dates.py` | `GET /sales/trend?fill_missing_dates=true` | 7 行、`meta.filled=true`、1/21–23 补零 |
| C5 | 400/80 在本语料实际退化为页级 chunk，文档却暗示生效；如实说明 + 150/400 对比实测 | `task2_rag/README.md`、`docs/.book/build.py`、`scripts/chunk_compare.py` | `python -B scripts/chunk_compare.py` | 150 → 83 chunks / 132.5；400 → 40 chunks / 242.6；均覆盖 36/36 页 |
| C6 | `.gitignore` 缺失且与"随包提供"矛盾；补齐忽略项 + `!` 反排除 DB/索引 | `.gitignore`、`task1_data_api/README.md` | `git status --short` | 缓存/临时库均不出现；`sales.duckdb` 与索引 `*.pkl` 保留 |

## 二、第二轮：按评分维度补强（鲁棒性 + 量化）

| ID | 改了什么 | 涉及文件 | 验证结果 |
|---|---|---|---|
| R1 | **归一化泛化**：组合词切分（MaxiDress）、斜杠/竖线/分号分隔、复数还原（Maxi Dresses）、全角（NFKC；SQL 侧 translate 等价折半） | `src/normalize.py`、`sql/02_dwd_tag.sql` | G1 类 5 条样本全过 |
| R2 | **拼写容错**：核心词 Damerau-Levenshtein ≤1 变体映射，先剔除同形词黑名单（maxim/maximum/address…），避免纠错引入假阳性 | 同上 | `Maxy/Dres/Dresss` → core；`Maxim Dress`、`Address Dress` 仍 excluded |
| R3 | **属性词语境**：mini/midi 紧跟 31 个属性词（print/length/sleeve/fit/petite…）时是修饰语不算档位——修复"Maxi Dress Midi Length 被误杀成 excluded"的口径污染 | 同上 | G3 误杀 0；`Midi Maxi Dress` 判 R6 灰区而非静默排除 |
| R4 | **档位冲突规则 R6**：mini/midi 与 maxi 同时为主档位 → gray_zone 待人工确认，不沉默丢弃 | 同上 | 真实数据 R6=0，基线不变 |
| R5 | **打标冲突检测**：`dim_product` 加 `title_variants`/`tag_conflict`；dq 第 6 条规则 `tag_conflict_detection`（warn）；API 返回冲突标识 | `01_dwd_schema.sql`、`src/ingest.py`、`src/api.py`、`docs/dq_report.md`、`mapping.xlsx` | 真实 300 行 0 冲突；合成用例 `9001 Maxi Dress Floral + Midi Dress Blue` → `tag_conflict=true` 且变体全保留 |
| R6 | **对抗样本回归**：28 条题面外样本固化进测试（G1–G6 + 7 条负样本），SQL 版同批灌库比对 | `tests/test_robustness.py`、`docs/design.md` §4.1/§4.2 | **28/28 通过、G3 误杀 0、SQL/Python 零差异** |
| R7 | **检索质量量化**：36 条人工标注（30 主题 + 6 口语/混写变体），`scripts/eval_retrieval.py` 出三档 recall@5 / MRR@10 / nDCG@10 | `eval/retrieval_eval.jsonl`、`scripts/eval_retrieval.py`、`docs/retrieval_eval.md`、`docs/eval.md`、README | 0.655/0.728/0.680 → +扩展 0.623/0.684/0.637 → +rerank **0.698/0.834/0.742**；并如实披露"扩展降低主题类 recall、提升变体召回" |
| R8 | **T2-I 鲁棒性**：查询变体入标注集；索引落盘语料指纹 `meta.json` + `check_freshness()`（插页重建告警）；`validate_inputs()` 统一空主题/纯符号/top-k≤50（CLI 与 Demo 同套）；`parse.sanitize()` 编码兜底 | `src/index.py`、`src/parse.py`、`pipeline.py`、`app.py`、`tests/test_t2_robustness.py` | 插页模拟检测命中；`pipeline "？"` 明确报错；非法字符剔除有计数 |

## 三、产物重建与基线核验

| 项 | 状态 |
|---|---|
| `data/sales.duckdb` | 删库重建（批次 `20261123T052700Z` / 幂等重跑 `20261123T052705Z`）；300→12→288、DWS 111、core12/gray1/excluded17、rule_counts 不变 |
| `examples/*.json` | TestClient 真实请求重建 7 份；products 12 条含 `tag_rule/title_variants/tag_conflict` |
| `data/index/bm25.pkl` + `meta.json` | 索引重建并落语料指纹；40 chunks / 36 页 / 均值 242.6 不变 |
| `docs/方案书.pdf` | 重生成：6 页、0 `**`、0 豆腐块；§2.4 铁律以真加粗渲染；新增 R6/对抗样本/检索量化/鲁棒性内容 |
| `docs/mapping.xlsx` | 三 Sheet 重排：字段映射含新列、归一化规则 11 步 + R1~R6、质量报告 6 条规则与新批次 |
| 三份 README + design/checklist/dq_report/eval | 与最终代码逐项对齐（87/56/31 passed、7 快照、6 条 DQ 规则、R1~R6） |

基线逐项复测保持一致：300→12→288、幂等 inserted=0、DWS 111（core100/gray11）、core 总销量 1117（core+gray 1217、全量 2717）、UTC≥16 跨天 132（源）/126（去重后）、40 chunks/36 页/242.6、示例文章 2060/2066 字引用 6/6、拒答样例 `refuse`、guard 14 主题 14/14。

## 四、诚实说明

1. **打标粒度仍是商品级**：冲突检测做到了"可发现、可复核"（tag_conflict + dq warn + API 可见），但没有把 `tag_status` 下沉到事实行级——真实数据 0 冲突，行级下沉会动 DWS 聚合路径，收益为零、风险不为零。生产化方向写进 design.md §4.2。
2. **检索标注是单一标注者**：36 条标注依据页面标题与正文首段判定，无交叉校验，换人可能有 ±5% 波动；已在 eval.md 明确标注，生产应双人标注 + Kappa。
3. **术语扩展对主题类查询 recall@5 有轻微负作用（0.755→0.692）**：如实披露而非调参掩盖；口语变体 recall@5 0.444 仍是短板，列入已知局限。
4. **方案书行距由 1.52 微调至 1.47**：为容纳第二轮新增内容并保持 6 页，纯排版参数，不影响内容。
5. **约束遵守**：未修改 `data_raw/` 三个原始文件；未把真实 `.env` 放进交付目录；未 `pip install`；未替换 `requirements.txt` 的 `httpx2`；全程 `-B` + `PYTHONDONTWRITEBYTECODE=1`；交付目录无 `__pycache__`/`.pytest_cache`/临时库，eval/outputs 保持原有 3 份真实产物。
