# OpenAI Validation Claim 自动申请

自动填表提交 OpenAI 非营利组织验证表单（Goodstack / Powered by Percent）。

## 流程

1. 入口 `validate.poweredbypercent.com/openai` → 302 含 `validationinvite_*` 和 JWT
2. 国家 = 日本 (JPN)，申请人固定 = 川博
3. 从内閣府 `npo-homepage.go.jp/npoportal/download/all` 取日本 NPO 全件 → 抽未用过且含法人番号(13位)的 NPO
4. 用 13 位法人番号在 Goodstack `v1/organisations` 命中已收录的 `organisationId`
5. cfmail worker 的 org 域名 + 随机罗马字人名前缀生成联系邮箱（通过 Goodstack advanced-email-validation）
6. POST `v1/validation-submissions`，本地 SQLite 去重
7. 轮询 cfmail 收件 / 验证码

## 后端

**本地开发**

```powershell
.\scripts\run.ps1
# 或
cd backend; .venv\Scripts\activate; uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器：http://127.0.0.1:8765/

**Docker（生产，sub2 服务器）**

```bash
docker compose up -d --build
```

环境变量见 `.env.example` → 重命名为 `.env`。

## API

| Method | Path | 作用 |
|--------|------|------|
| POST | `/api/npo/refresh?idx_list=0` | 下载导入 NPO 全件 |
| GET | `/api/npo/stats` | NPO 库统计 |
| GET | `/api/npo/preview?limit=10` | 随机预览 |
| POST | `/api/claim/one` | 抽 1 条 + 提交 |
| POST | `/api/claim/batch?count=N` | 批量 1-20 |
| GET | `/api/claim/history?limit=50` | 历史 |
| GET | `/api/claim/{id}/mails` | 收信 |
| GET | `/api/claim/{id}/code` | 取最新验证码 |
| GET | `/api/mail/inbox?address=`、`/api/mail/code?address=` | cfmail 直查 |
| POST | `/api/mail/send` | cfmail 发信（需 `CFMAIL_SEND_TOKEN`） |

## Goodstack API

- Base: `https://api.goodstack.io/`
- Header: `Authorization: <partnerPublicKey>`
- 关键端点：`v1/countries`、`v1/organisations`、`v1/registries`、`v1/advanced-email-validation/results?email=`、`v1/validation-submissions` (POST)

## cfmail worker

- Base: `https://cfmail.lk1950.online`
- 收信：`GET /api/mails?address=...`
- 取验证码：`GET /api/code?address=...`
- 发信：`POST /api/send`（Bearer `SEND_TOKEN`）

## License

MIT