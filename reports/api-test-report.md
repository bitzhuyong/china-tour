# API 端点测试报告

> 生成时间: 2026-03-27T13:16:51.256813
> API URL: http://1.13.252.172:3000

## 概览

| 指标 | 值 |
|------|-----|
| 总测试数 | 7 |
| 通过 | 5 |
| 失败 | 2 |
| 通过率 | 5/7 (71%) |

## 测试结果

| 端点 | 方法 | 描述 | 状态码 | 耗时 | 结果 |
|------|------|------|--------|------|------|
| /api/v1/guide/health | GET | Health check endpoint | 0 | 60026ms | FAIL |
| /api/v1/guide/attractions | GET | List attractions | 200 | 84ms | OK |
| /api/v1/guide/attractions?limit=5 | GET | List attractions with limit | 200 | 84ms | OK |
| /api/v1/guide/attractions?search=故宫 | GET | Search attractions | 200 | 90ms | OK |
| /api/v1/guide/ask | POST | Ask question (basic) | 200 | 102ms | OK |
| /api/v1/guide/ask | POST | Ask question (English) | 200 | 78ms | OK |
| /api/v1/guide/scenic/1 | GET | Get scenic info (if exists) | 404 | 90ms | FAIL |

## 问题列表

- GET /api/v1/guide/health: Request timed out
- GET /api/v1/guide/scenic/1: Scenic spot not found
