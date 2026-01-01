================================================================================
python : Traceback (most recent call last):
所在位置 C:\Users\jame\AppData\Local\Temp\ps-script-74e86ead-e3b3-4544-bcda-170f73a4a00b.ps1:111 字符: 1
+ python scripts/analyze_code_quality.py 2>&1 | Out-File -Encoding utf8 ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (Traceback (most recent call last)::String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
  File "D:\aquatrade\scripts\analyze_code_quality.py", line 187, in <module>
代码质量分析报告
================================================================================


## SERVER 模块
--------------------------------------------------------------------------------
总文件数: 9
总代码行数: 5,809
总函数数: 92
总类数: 1

[WARN] 发现的问题:
  - server\app.py: 文件过大 (2466 行)
  - server\app.py: 函数过多 (53 个)
  - server\app.py: 嵌套过深 (深度 15)
  - server\app.py: 发现 4 个重复模式
  - server\asgi_socketio_handlers.py: 嵌套过深 (深度 15)
  - server\performance_utils.py: 发现 1 个重复模式
  - server\visualization_api.py: 文件过大 (2081 行)
  - server\visualization_api.py: 嵌套过深 (深度 10)

[INFO] 最大的文件:
  - server\app.py: 2,466 行
  - server\visualization_api.py: 2,081 行
  - server\asgi_socketio_handlers.py: 467 行
  - server\asgi_entry.py: 198 行
  - server\routes\sentiment_routes.py: 184 行


## CORE 模块
--------------------------------------------------------------------------------
总文件数: 26
总代码行数: 8,892
总函数数: 183
总类数: 25

[WARN] 发现的问题:
  - core\gpu_engine.py: 嵌套过深 (深度 7)
  - core\backtest\optimization_engine.py: 文件过大 (1375 行)
  - core\backtest\optimization_engine.py: 嵌套过深 (深度 7)
  - core\backtest\optimized_backtest_engine.py: 文件过大 (1472 行)
  - core\strategies\apex_convergence_strategy.py: 发现 1 个重复模式
  - core\strategies\example_vectorized_strategy.py: 发现 1 个重复模式
  - core\strategies\strategy_factory.py: 发现 6 个重复模式
  - core\utils\gpu_acceleration.py: 嵌套过深 (深度 6)
  - core\utils\indicator_calculator.py: 嵌套过深 (深度 7)
  - core\utils\indicator_calculator.py: 发现 2 个重复模式
  - core\utils\redis_socketio_publisher.py: 发现 4 个重复模式

[INFO] 最大的文件:
  - core\backtest\optimized_backtest_engine.py: 1,472 行
  - core\backtest\optimization_engine.py: 1,375 行
  - core\gpu_engine.py: 577 行
  - core\strategies\jq_volume_strategy.py: 523 行
  - core\strategies\apex_convergence_strategy.py: 502 行


## DATA_SVC 模块
--------------------------------------------------------------------------------
总文件数: 28
总代码行数: 8,694
总函数数: 150
总类数: 6

[WARN] 发现的问题:
  - data_svc\lance_manager.py: 发现 1 个重复模式
  - data_svc\database\fast.py: 嵌套过深 (深度 7)
    main()
  - data_svc\database\tushare_updater.py: 嵌套过深 (深度 6)
  - data_svc\spider\1.py: 文件过大 (1470 行)
  - data_svc\spider\1.py: 嵌套过深 (深度 10)
  - data_svc\spider\app.py: 文件过大 (1368 行)
  - data_svc\spider\app.py: 函数过多 (33 个)
  - data_svc\spider\app.py: 嵌套过深 (深度 13)
  - data_svc\spider\app.py: 发现 4 个重复模式
  File "D:\aquatrade\scripts\analyze_code_quality.py", line 182, in main
  - data_svc\spider\crawl_stock_posts.py: 嵌套过深 (深度 7)

[INFO] 最大的文件:
  - data_svc\spider\1.py: 1,470 行
  - data_svc\spider\app.py: 1,368 行
  - data_svc\database\data_processor_fast.py: 749 行
  - data_svc\lance_manager.py: 600 行
  - data_svc\spider\crawl_stock_posts.py: 562 行

    with open(report_file, 'w', encoding='utf-8') as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: 'D:\\aquatrade\\docs\\CODE_QUALITY_ANALYSIS.md'
