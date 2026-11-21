# examples/：真实请求落盘的响应快照

> 全部由运行中的服务真实返回（`GET` + `python -m json.tool` 格式化），评审可直接看，不用起服务。

| 文件 | 请求 | 状态码 | 说明 |
|---|---|---|---|
| `trend-website.json` | `GET /api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&platforms=website` | 200 | 典型成功响应：`meta/count/data` 三段式。`count=4` 而非 7——无销售记录的日子不返回行（GROUP BY 自然行为），前端画趋势图需按日期补零 |
| `trend-gray-on.json` | `GET /api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&include_gray_zone=true` | 200 | 不限平台 + 计入灰区：`count=6`，1/23 出现 app 平台 gray_zone 销量 9 件。对照上一条可见 platforms 过滤的直接影响 |
| `error-400.json` | `GET /api/v1/sales/trend?start_date=2024-02-01&end_date=2024-01-01` | 400 | 业务规则错误（日期倒序）：`detail` 为字符串，可直接展示 |
| `error-422.json` | `GET /api/v1/sales/trend?start_date=2024-01-01` | 422 | pydantic 参数校验失败（缺 end_date）：`detail` 为数组，含 `loc`/`msg`，为框架层自动生成 |
| `products-core.json` | `GET /api/v1/products?tag=core` | 200 | 商品维表按打标结果过滤：core 12 个商品 |
| `healthz.json` | `GET /healthz` | 200 | 存活探针 + 事实表行数（288 = 300 输入 − 12 重复） |

复现命令示例：

```bash
curl "http://127.0.0.1:8000/api/v1/sales/trend?start_date=2024-01-20&end_date=2024-01-26&platforms=website"
```
