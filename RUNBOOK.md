# AquaTrade 运行手册

## 环境

- 项目目录：`C:\Users\Liu\Desktop\projects\aquatrade`
- 后端默认端口：`5000`
- 前端默认端口：`5173`
- Windows 终端建议设置：`$env:PYTHONIOENCODING='utf-8'`

## 启动

后端：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m server.app
```

前端：

```powershell
cd myapp
npm run dev -- --host 127.0.0.1 --port 5173
```

访问：`http://127.0.0.1:5173/dashboard`

## 数据健康

```powershell
python scripts/generate_data_health.py
```

输出：

- `data/reports/data_health_latest.json`
- `data/reports/data_health_latest.md`
- `DATA_MAP.generated.md`

接口：`GET http://127.0.0.1:5000/api/data/health`

## QuantFlow

```powershell
python -m core.pipeline.quant_flow_pipeline
```

输出：

- `data/reports/quant_flow_latest.json`
- `data/reports/quant_flow_latest.md`

接口：

- `GET /api/quant-flow/latest`
- `POST /api/quant-flow/run`

## QMT/QNT Dry-run

```powershell
python -m integrations.qmt_bridge.dry_run_demo
```

输出：`data/reports/qmt_bridge_dry_run_latest.json`

必须确认：

- `dry_run` 为 `true`
- `real_broker_connected` 为 `false`
- 订单来源为 `mock_broker`

## 验证

```powershell
python -m compileall server core data_svc integrations scripts
python scripts/smoke_api_routes.py
python -m pytest test/test_frontend_api_integration.py -q
cd myapp
npm run build
```

## 数据降级规则

- 本地证据为空：显示“暂无本地证据”。
- 无回测结果：不自动加载 Mock。
- 交易次数为 0：胜率和盈亏比显示 `N/A`。
- 真实 broker：当前不可用，调用时抛出 `NotImplementedError`。
