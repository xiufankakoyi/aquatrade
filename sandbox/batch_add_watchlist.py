"""
批量添加自选股脚本
通过股票名称查找代码并添加到自选列表
"""
import sys
sys.path.insert(0, '.')

from server.services.data_initialization_service import DataInitializationService

STOCK_NAMES = [
    "通富微电",
    "华天科技",
    "长飞光纤",
    "福晶科技",
    "金安国纪",
    "中钨高新",
    "宏和科技",
    "风华高科",
    "招商南油",
    "桐昆股份",
    "东方电气",
    "深南电路",
    "华正新材",
    "思源电气",
    "伊戈尔",
    "兆易创新",
    "中国巨石",
    "中材科技",
    "长电科技",
    "德明利",
    "生益科技",
    "航天电子",
    "光启技术",
    "航发动力",
    "中金黄金",
    "中远海能",
    "山东赫达",
    "鼎胜新材",
    "宏达股份",
]


def find_stock_code(name: str, stock_info_map: dict) -> tuple:
    """
    根据股票名称查找股票代码
    返回 (code, name) 或 (None, None)
    """
    for code, stock_name in stock_info_map.items():
        if name in stock_name or stock_name in name:
            return code, stock_name
    return None, None


def main():
    print("=" * 60)
    print("批量添加自选股")
    print("=" * 60)

    init_service = DataInitializationService()
    init_service.ensure_initialized()

    stock_info_map = init_service.stock_info_map
    print(f"股票信息库: {len(stock_info_map)} 条记录")

    found_stocks = []
    not_found = []

    for name in STOCK_NAMES:
        code, full_name = find_stock_code(name, stock_info_map)
        if code:
            found_stocks.append({
                "stock_code": code,
                "stock_name": full_name,
                "conditions": [],
                "notes": "",
                "tags": [],
                "is_active": True,
                "feishu_notify": True
            })
            print(f"✓ {name}: {code} - {full_name}")
        else:
            not_found.append(name)
            print(f"✗ {name}: 未找到")

    print()
    print(f"找到: {len(found_stocks)} 只, 未找到: {len(not_found)} 只")

    if not_found:
        print(f"\n未找到的股票: {not_found}")

    if found_stocks:
        print("\n" + "=" * 60)
        print("准备添加到自选列表...")
        print("=" * 60)

        import requests

        url = "http://localhost:5000/api/portfolio/watchlist/batch"
        response = requests.post(url, json={"items": found_stocks})

        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"✓ 成功添加 {result['data']['added_count']} 只股票到自选列表")
                if result['data'].get('skipped_count', 0) > 0:
                    print(f"  跳过 {result['data']['skipped_count']} 只已存在的股票")
            else:
                print(f"✗ 添加失败: {result.get('error')}")
        else:
            print(f"✗ 请求失败: {response.status_code}")

    print("\n完成!")


if __name__ == "__main__":
    main()
