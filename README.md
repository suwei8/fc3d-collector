# fc3d-collector

福彩3D 数据采集器。定时运行（北京时间 18:25 / 18:55 / 19:35 / 21:30 / 22:10），
从天齐网、彩之家、牛彩网等公开来源采集试机号与字谜数据。

本仓库只存放采集代码与调度工作流，**不存储数据**。采集结果由 GitHub Actions
通过 deploy key 推送至私有归档仓库 `suwei8/fc3d-archive`。

## 本地运行

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q
python scripts/collect.py            # 采集最新期（写入本仓库 data/ raw/）
```

将 `FC3D_ROOT` 指向归档仓库的本地 checkout，即可把采集结果写入归档：

```bash
FC3D_ROOT=/path/to/fc3d-archive python scripts/collect.py
```

## Telegram 推送

归档仓库有数据变更时，自动把最新一期记录推送到 Telegram。
需要在仓库 Settings → Secrets and variables → Actions 配置：

- `TELEGRAM_BOT_TOKEN`：BotFather 颁发的 bot token
- `TELEGRAM_CHAT_ID`：接收消息的 chat id

平时仅在归档有数据变更时推送；手动触发可勾选 `test_notify` 强制推一条
（用于验证 secrets 配置）。

## 手动触发

Actions → collect → Run workflow，可选参数：

- `issue`：采集指定期号
- `from_issue` / `to_issue`：区间回填
