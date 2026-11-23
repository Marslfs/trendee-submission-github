# examples/：真实请求落盘的响应快照

> 全部由运行中的服务真实返回（`GET` + `python -m json.tool` 格式化），评审可直接看，不用起服务。

| 文件 | 请求 | 状态码 | 说明 |
|---|---|---|---|
| `trend-website.json` | `GET /api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&platforms=website` | 200 | 典型成功响应：`meta/count/data` 三段式，`count=4`（只有 4 天有销售记录）。**用 `fill_missing_dates=true` 可让服务端补零返回完整 7 天**，不再需要前端自己补零，示例见 `trend-filled.json` |
| `trend-filled.json` | 同上 + `&fill_missing_dates=true` | 200 | 服务端补齐空缺日期：`count=7`、`meta.filled=true`，无数据日为 `total_sales:0 / records:0 / by_platform:{}` |
| `trend-gray-on.json` | `GET /api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&include_gray_zone=true` | 200 | 不限平台 + 计入灰区：`count=6`，1/23 出现 app 平台 gray_zone 销量 9 件。对照上一条可见 platforms 过滤的直接影响 |
| `error-400.json` | `GET /api/v1/sales/trend?start_date=2024-02-01&end_date=2024-01-01` | 400 | 业务规则错误（日期倒序）：`detail` 为字符串，可直接展示 |
| `error-422.json` | `GET /api/v1/sales/trend?start_date=2024-01-01` | 422 | pydantic 参数校验失败（缺 end_date）：`detail` 为数组，含 `loc`/`msg`，为框架层自动生成 |
| `products-core.json` | `GET /api/v1/products?tag=core` | 200 | 商品维表按打标结果过滤：core 12 个商品 |
| `healthz.json` | `GET /healthz` | 200 | 存活探针 + 事实表行数（288 = 300 输入 − 12 重复） |

复现命令示例：

```bash
curl "http://127.0.0.1:8000/api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&platforms=website"
# 服务端补零（返回完整 7 天）
curl "http://127.0.0.1:8000/api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&platforms=website&fill_missing_dates=true"
```

全部快照由 `python scripts/snap_examples.py`（TestClient 真实请求）重建，API 变更后重跑即可。
