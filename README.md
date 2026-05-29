# SPY/QQQ DCA Reminder

这个项目用于在 GitHub Actions 上每 5 分钟检查 SPY 和 QQQ，并通过 Telegram 发送定投提醒。

## 规则

- SPY 和 QQQ 各自独立计算、独立去重。
- 第一次定投：当月首次出现 `当前价 / 昨收 - 1 <= -1.5%`。
- 如果当月第一次定投没有触发，则在最后一个交易日开盘前 `09:00-09:29 ET` 提醒。
- 第二次定投：当月首次出现 `当前价 / 月初首个交易日开盘 - 1 <= -5%`。
- 第三次定投：当前价同时低于 MA20 和 MA50 的 85%。
- 每个标的每月最多发送三类提醒各一次。

## GitHub Secrets

在仓库 `Settings > Secrets and variables > Actions` 添加：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

不要把 token、chat id 或 `.env` 提交到仓库。

## GitHub Actions

`.github/workflows/monitor.yml` 每 5 分钟触发一次。GitHub 的定时任务可能延迟，程序内部会再次判断是否处于 NYSE 交易日、正常交易窗口或月末开盘前提醒窗口。

## 本地验证

```powershell
python -m pip install -e ".[dev]"
pytest
```

只打印消息、不真实发送 Telegram：

```powershell
$env:DRY_RUN = "1"
python -m dca_reminder.main
```
