/**
 * 端到端测试删除功能 - 使用Playwright或类似工具
 * 这里先用简单的fetch测试模拟浏览器行为
 */

// 模拟浏览器中的fetch删除请求
async function testBrowserDelete() {
  const BASE_URL = "http://localhost:5000";

  console.log("=" .repeat(70));
  console.log("端到端测试 - 模拟浏览器删除请求");
  console.log("=" .repeat(70));

  // 1. 先获取持仓
  console.log("\n[1] 获取当前持仓...");
  const getResponse = await fetch(`${BASE_URL}/api/portfolio/positions?active_only=true`);
  const data = await getResponse.json();

  if (!data.success || data.data.length === 0) {
    console.log("没有持仓可测试");
    return true;
  }

  const positions = data.data;
  console.log(`获取到 ${positions.length} 条持仓`);

  const target = positions[0];
  console.log(`\n准备删除: ID=${target.id}, ${target.stock_code} ${target.stock_name}`);

  // 2. 模拟浏览器的DELETE请求（带CORS头）
  console.log("\n[2] 发送DELETE请求（模拟浏览器）...");
  try {
    const deleteResponse = await fetch(`${BASE_URL}/api/portfolio/positions/${target.id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:5173'
      },
      mode: 'cors',
      credentials: 'include'
    });

    console.log(`  状态码: ${deleteResponse.status}`);
    console.log(`  CORS头: ${deleteResponse.headers.get('Access-Control-Allow-Origin') || 'N/A'}`);

    const deleteData = await deleteResponse.json();
    console.log(`  响应: ${JSON.stringify(deleteData)}`);

    if (!deleteData.success) {
      console.log("  ❌ 删除失败");
      return false;
    }

    console.log("  ✅ 删除成功");

    // 3. 验证删除
    console.log("\n[3] 验证删除结果...");
    const verifyResponse = await fetch(`${BASE_URL}/api/portfolio/positions?active_only=true`);
    const verifyData = await verifyResponse.json();

    const remainingIds = verifyData.data.map(p => p.id);
    if (remainingIds.includes(target.id)) {
      console.log("  ❌ 持仓仍然存在！");
      return false;
    }

    console.log("  ✅ 验证通过");
    console.log("\n" + "=" .repeat(70));
    console.log("✅ 端到端测试通过！");
    console.log("=" .repeat(70));

    return true;

  } catch (error) {
    console.log(`  ❌ 请求错误: ${error.message}`);
    return false;
  }
}

testBrowserDelete().then(success => {
  process.exit(success ? 0 : 1);
});
