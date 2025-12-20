// 使用PowerShell测试策略API的脚本
// 请直接运行: node test_strategies_api.js

console.log('请在PowerShell中运行以下命令测试策略API:');
console.log(`
# 测试策略API命令
$response = Invoke-RestMethod -Uri "http://localhost:5000/api/strategies" -Method Get
Write-Host "API响应类型: $($response.GetType().FullName)"
Write-Host "响应内容:" -ForegroundColor Cyan
ConvertTo-Json $response -Depth 3

# 检查数据结构
if ($response -and $response.success -and $response.data -is [array]) {
    Write-Host "\n策略列表数据结构正确!" -ForegroundColor Green
    Write-Host "策略数量: $($response.data.Length)" -ForegroundColor Yellow
    $response.data | ForEach-Object -Begin { $i = 1 } -Process { 
        Write-Host "策略 $i: $($_.name) (ID: $($_.id))" -ForegroundColor Magenta
        $i++
    }
} else {
    Write-Host "\n警告: 数据结构不符合预期" -ForegroundColor Red
    Write-Host "success: $($response.success)" -ForegroundColor Red
    Write-Host "data类型: $($response.data.GetType().FullName)" -ForegroundColor Red
}
`);

// 简单的修复建议
console.log(`
// 前端代码修复建议:
// 在GridSearchPage.vue中，确保availableStrategies被正确赋值，并且添加默认选项
// 另外确保select的v-model绑定正确设置`);
