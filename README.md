# trendee-assessment｜万悉科技 AI 数据工程师笔试

> 环境与骨架已就绪，业务实现进行中（2 天窗口）。

## 快速开始（占位）

```bash
# 1) 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows CMD / Git Bash
# .venv\Scripts\Activate.ps1    # Windows PowerShell

# 2) 安装依赖
pip install -r requirements.txt

# 3) 配置（复制后填入真实值）
copy .env.example .env

# 4) 运行（占位）
# task1: uvicorn src.api:app --reload        （待实现）
# task2: streamlit run app.py                （待实现）
```

## 项目结构

```
task1_data_api/   销售数据 → DuckDB + FastAPI
task2_rag/        品宣 PDF → RAG 写作系统
data_raw/         三份原始材料（笔试题 PDF / 样例销售数据 xlsx / 品宣 PDF）
```
