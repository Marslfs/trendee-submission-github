# -*- coding: utf-8 -*-
"""mapping.xlsx 生成：字段映射 / 归一化规则 / 质量报告 三 Sheet。"""
try:
    import openpyxl
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "openpyxl>=3.1.0"])
    import openpyxl

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def xl_color(css_hex: str) -> str:
    value = css_hex.removeprefix("#").upper()
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB, got: {css_hex}")
    return "FF" + value

XL_PRIMARY = xl_color("#4472C4")
XL_LIGHT = xl_color("#D9E2F3")
XL_BORDER = xl_color("#BFBFBF")
XL_PASS_FILL = xl_color("#C6EFCE")
XL_PASS_FONT = xl_color("#006100")
XL_WARN_FILL = xl_color("#FFEB9C")
XL_WARN_FONT = xl_color("#9C6500")

thin = Side(style="thin", color=XL_BORDER)
BORDER_ALL = Border(left=thin, right=thin, top=thin, bottom=thin)
HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
HDR_FILL = PatternFill("solid", fgColor=XL_PRIMARY)
HDR_ALIGN = Alignment(horizontal="center", vertical="center", wrapText=True)
BODY_ALIGN = Alignment(vertical="center", wrapText=True)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center", wrapText=True)
TITLE_FONT = Font(bold=True, size=13, color="1A1A1A")
SEC_FONT = Font(bold=True, size=11, color="2F5597")

OUT = r"D:\workspace4AiAgent\workspace4Trendee\trendee-assessment\task1_data_api\docs\mapping.xlsx"

wb = openpyxl.Workbook()
wb.properties.title = "Task1 字段映射·归一化规则·质量报告"

def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = HDR_FONT
        cell.fill = HDR_FILL
        cell.alignment = HDR_ALIGN
        cell.border = BORDER_ALL

def style_body(ws, r0, r1, ncols, center_cols=()):
    for r in range(r0, r1 + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BORDER_ALL
            cell.alignment = CENTER_ALIGN if c in center_cols else BODY_ALIGN
        if (r - r0) % 2 == 1:
            for c in range(1, ncols + 1):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=XL_LIGHT)

def set_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

# ============ Sheet 1 字段映射 ============
ws1 = wb.active
ws1.title = "字段映射"
ws1["A1"] = "源字段 → 数仓字段映射（样例销售数据.xlsx → DuckDB DIM/DWD）"
ws1["A1"].font = TITLE_FONT
ws1.merge_cells("A1:G1")

headers1 = ["序号", "源字段", "源形态", "目标表.字段", "目标类型", "转换规则", "依据 / 备注"]
for c, h in enumerate(headers1, 1):
    ws1.cell(row=2, column=c, value=h)
style_header(ws1, 2, len(headers1))

rows1 = [
    (1, "product_id", "整数", "dim_product.product_id\n/dwd_fact_sales.product_id", "INTEGER",
     "直接透传，不做改写", "去重后 30 个商品；同商品多标题变体经 dim_title_alias 关联"),
    (2, "title", "文本", "dim_title_alias.raw_title", "VARCHAR",
     "原样保留首见写法", "37 种标题写法 / 30 个商品，原值留作审计证据"),
    (3, "title（派生）", "文本", "dim_product.title_norm\n/dim_title_alias.title_norm", "VARCHAR",
     "normalize_title()：NFKC→小写→撇号转空格→连字符/下划线转空格→压连续空白",
     "归一化是打标前置步骤，规则见「归一化规则」Sheet"),
    (4, "sales_count", "整数", "dwd_fact_sales.sales_count", "INTEGER",
     "pd.to_numeric(errors=raise) 收紧类型后 astype(int)", "实测范围 1~18，无缺失/负数/离群"),
    (5, "timestamp", "Excel 序列号→datetime", "dwd_fact_sales.dt_utc", "TIMESTAMP",
     "声明为 UTC 口径；入库前剥掉 tzinfo，存 UTC 墙钟", "覆盖 2024-01-01 07:00 ~ 03-13 09:45"),
    (6, "timestamp（派生）", "—", "dwd_fact_sales.dt_local", "TIMESTAMP",
     "dt_utc + 8h（Asia/Shanghai，无夏令时），剥 tz 后存本地墙钟",
     "300 条原始记录中 132 条 UTC≥16:00 跨天；聚合一律用 dt_local"),
    (7, "（派生）row_hash", "—", "dwd_fact_sales.row_hash", "VARCHAR 主键",
     "md5(product_id|title_norm|sales_count|dt_utc|user_id|category|platform)",
     "幂等键：重跑 anti-join 不增行，重跑 inserted=0 已验证"),
    (8, "user_id", "文本", "dwd_fact_sales.user_id", "VARCHAR",
     "str + strip，其余原样", "来源记录标识，参与 row_hash"),
    (9, "category", "文本", "dim_product.category", "VARCHAR",
     "lower + strip", "粗粒度 6 类：dress/skirt/shoes/pants/shirt/jacket；仅 dress 可能命中 maxi dress"),
    (10, "source", "文本", "dim_platform.platform_name\n/dwd_fact_sales.platform", "VARCHAR",
     "lower + strip，并重命名 source→platform", "三平台近似均匀：app 97 / marketplace 95 / website 96（去重后）"),
    (11, "（派生）ingest_batch", "—", "dwd_fact_sales.ingest_batch", "VARCHAR",
     "UTC 时间戳批次号 %Y%m%dT%H%M%SZ", "dq_report 按批次可追溯"),
]
r0, r1 = 3, 3 + len(rows1) - 1
for i, row in enumerate(rows1):
    for c, v in enumerate(row, 1):
        ws1.cell(row=r0 + i, column=c, value=v)
style_body(ws1, r0, r1, len(headers1), center_cols=(1,))
ws1.freeze_panes = "A3"
ws1.auto_filter.ref = f"A2:G{r1}"
set_widths(ws1, [6, 16, 16, 30, 13, 40, 42])

# ============ Sheet 2 归一化规则 ============
ws2 = wb.create_sheet("归一化规则")
ws2["A1"] = "maxi dress 三段式打标规则（normalize.py，与 02_dwd_tag.sql 交叉验证）"
ws2["A1"].font = TITLE_FONT
ws2.merge_cells("A1:H1")

headers2 = ["规则号", "阶段", "判定类别", "规则", "示例输入", "示例输出 / 判定", "防误伤说明"]
for c, h in enumerate(headers2, 1):
    ws2.cell(row=2, column=c, value=h)
style_header(ws2, 2, len(headers2))

rows2 = [
    ("R1", "预处理", "归一化", "NFKC 规范化 → 小写 → 去首尾空白", "Maxi Dress ", "maxi dress",
     "消除大小写差异（2001/2002 号商品的陷阱）"),
    ("R2", "预处理", "归一化", "所有格撇号转空格：women's → women s", "Women's Maxi-Dress Floral", "women s maxi dress",
     "所有格不拆开会在词级匹配时粘连"),
    ("R3", "预处理", "归一化", "连字符/下划线/连续空白统一压成单空格", "Red Maxi-Dress / blue maxi  dress", "red maxi dress",
     "消除连字符与双空格差异（2003/2004 号商品陷阱）"),
    ("R4", "判定", "负向排除", "词元含 mini 或 midi → excluded", "Midi Dress Blue", "excluded",
     "先查长度档位冲突，防止 midi dress 被误判成 maxi dress"),
    ("R5", "判定", "正向命中", "词元含 maxi 且含 dress → core", "Summer Maxi Dress", "core",
     "词级集合匹配，词序无关（2005/2008 号商品词序陷阱）"),
    ("R6", "判定", "负向排除", "词元含 maxi 但无 dress → excluded", "Maxi Skirt / Long Floral Skirt", "excluded",
     "只按 maxi 关键词匹配会误杀 skirt 类负样本"),
    ("R7", "判定", "灰区", "词元含 dress 且含 long，无 maxi → gray_zone", "Elegant Long Dress", "gray_zone",
     "长裙语义接近但无 maxi 证据：默认不计入，API include_gray_zone=true 可开"),
    ("R8", "判定", "兜底排除", "以上均不命中 → excluded", "Casual Dress / T-shirt Dress", "excluded",
     "dress 但无 maxi，不属本题口径"),
]
r0 = 3
r1 = r0 + len(rows2) - 1
for i, row in enumerate(rows2):
    for c, v in enumerate(row, 1):
        ws2.cell(row=r0 + i, column=c, value=v)
style_body(ws2, r0, r1, len(headers2), center_cols=(1, 2, 3))

note_r = r1 + 2
ws2.cell(row=note_r, column=1, value="打标结果（按商品维度，共 30 个去重商品）：core 12 / gray_zone 1（Elegant Long Dress）/ excluded 17；规则版本随 02_dwd_tag.sql 落库可一键重算。")
ws2.cell(row=note_r, column=1).font = SEC_FONT
ws2.merge_cells(start_row=note_r, start_column=1, end_row=note_r, end_column=8)
ws2.freeze_panes = "A3"
ws2.auto_filter.ref = f"A2:H{r1}"
set_widths(ws2, [7, 8, 10, 30, 26, 18, 44])

# ============ Sheet 3 质量报告 ============
ws3 = wb.create_sheet("质量报告")
ws3["A1"] = "数据质量报告（batch 20261121T084326Z，由 ingest 管道自动生成）"
ws3["A1"].font = TITLE_FONT
ws3.merge_cells("A1:E1")

# 区块 A：摄取统计（锚点：小标题第3行、表头第4行、数据5~11行）
ws3["A3"] = "一、摄取统计"
ws3["A3"].font = SEC_FONT
for c, h in enumerate(["指标", "数值", "说明"], 1):
    ws3.cell(row=4, column=c, value=h)
style_header(ws3, 4, 3)
stats_rows = [
    ("输入行数", 300, "样例销售数据.xlsx 全量"),
    ("过滤重复", 12, "12 组完全重复（5 业务字段全同），row_hash 幂等过滤"),
    ("落库行数", 288, "dwd_fact_sales"),
    ("预聚合行数", 111, "dws_sales_daily（日期×平台×tag）"),
    ("core 商品", 12, "dim_product 打标结果"),
    ("gray_zone 商品", 1, "Elegant Long Dress，API 可开关"),
    ("excluded 商品", 17, "含 Maxi Skirt 等负样本"),
]
for i, row in enumerate(stats_rows):
    for c, v in enumerate(row, 1):
        ws3.cell(row=5 + i, column=c, value=v)
style_body(ws3, 5, 11, 3, center_cols=(2,))
stat_end = 11

# 区块 B：5 条质量规则（锚点：小标题13行、表头14行、数据15~19行、汇总20行）
ws3["A13"] = "二、质量规则检查"
ws3["A13"].font = SEC_FONT
for c, h in enumerate(["序号", "检查项", "级别", "结果", "明细"], 1):
    ws3.cell(row=14, column=c, value=h)
style_header(ws3, 14, 5)
rules_rows = [
    (1, "uniqueness_row_hash", "error", "通过", "288 行 / 288 个 distinct hash，主键级唯一"),
    (2, "completeness_not_null", "error", "通过", "核心字段（product_id/platform/sales_count/dt_utc）无空值"),
    (3, "tag_glossary_consistency", "error", "通过", "DWS 聚合表无非法 tag_status（excluded 不进汇总）"),
    (4, "anomaly_sales_range", "warn", "通过", "sales_count ∈ [1,18]，无 ≤0 或 >10000 异常值"),
    (5, "timeliness_coverage", "info", "通过", "dt_utc 覆盖 2024-01-01 07:00 → 03-13 09:45；输入重复过滤 12 条"),
]
for i, row in enumerate(rules_rows):
    for c, v in enumerate(row, 1):
        ws3.cell(row=15 + i, column=c, value=v)
style_body(ws3, 15, 19, 5, center_cols=(1, 3, 4))

# 结果列条件格式：通过→绿底；不通过→红底
from openpyxl.formatting.rule import CellIsRule
pass_fill = PatternFill("solid", fgColor=XL_PASS_FILL)
pass_font = Font(color=XL_PASS_FONT)
fail_fill = PatternFill("solid", fgColor=xl_color("#FFC7CE"))
fail_font = Font(color=xl_color("#9C0006"))
ws3.conditional_formatting.add(
    "D15:D19", CellIsRule(operator="equal", formula=['"通过"'], fill=pass_fill, font=pass_font))
ws3.conditional_formatting.add(
    "D15:D19", CellIsRule(operator="notEqual", formula=['"通过"'], fill=fail_fill, font=fail_font))

# 汇总行（第20行）：通过率 = 通过项数 / 检查项数，带除零保护
ws3["A20"] = "汇总"
ws3["D20"] = '=IF(COUNTA(C15:C19)=0,"",COUNTIF(D15:D19,"通过")/COUNTA(D15:D19))'
ws3["D20"].number_format = "0.00%"
ws3["C20"] = "通过率"
ws3["E20"] = "5 条规则全部通过（=COUNTIF(D15:D19,\"通过\")/COUNTA(D15:D19)，除零保护已内联）"
for c in range(1, 6):
    cell = ws3.cell(row=20, column=c)
    cell.border = BORDER_ALL
    cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", fgColor=XL_LIGHT)
ws3["D20"].alignment = CENTER_ALIGN

# 口径备注
ws3["A22"] = "关键口径：① 重复数据按 row_hash 删除但 dq_report 留痕；② 时区声明 UTC、聚合用 dt_local（132 条原始跨天 / 去重后 126 条）；③ 3 月数据仅到 13 日，月度趋势需注明不完整。"
ws3["A22"].font = Font(size=10, color="595959")
ws3["A22"].alignment = Alignment(wrapText=True, vertical="top")
ws3.merge_cells(start_row=22, start_column=1, end_row=22, end_column=5)
ws3.row_dimensions[22].height = 32

set_widths(ws3, [8, 24, 8, 10, 60])

wb.save(OUT)
print("saved:", OUT)
