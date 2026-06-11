# QMT/QNT Bridge

当前模块只提供接口边界、风控检查和本地 dry-run。

- `BrokerBridge` 的真实交易方法全部抛出 `NotImplementedError`。
- `MockBrokerBridge` 只写本地 JSON，不连接券商、不读取真实账户。
- `RiskGuard` 缺少任一必需字段时拒绝计划。
- `dry_run_demo.py` 生成 `data/reports/qmt_bridge_dry_run_latest.json`，并明确标记 `dry_run: true`。

运行：

```bash
python integrations/qmt_bridge/dry_run_demo.py
```
