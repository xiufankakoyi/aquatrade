# 爬取股票帖子脚本使用说明

## 功能说明

这个脚本用于爬取指定股票在东方财富股吧近一年（或指定月数）的所有帖子。

## 使用方法

### 基本用法

```bash
python crawl_stock_posts.py --stock-code 000592
```

### 完整参数说明

```bash
python crawl_stock_posts.py \
    --stock-code 000592 \          # 股票代码（必需）
    --months 12 \                  # 爬取近N个月的帖子（默认12个月）
    --threads 5 \                  # 爬取线程数（默认5个）
    --fetch-content \              # 是否爬取帖子正文内容（可选）
    --max-pages 1000 \             # 最大爬取页数（默认1000页）
    --chromedriver-path "I:\chromedriver-win64\chromedriver.exe"  # ChromeDriver路径
```

### 参数详解

- `--stock-code`: **必需**，股票代码，如 `000592`（平潭发展）
- `--months`: 可选，爬取近N个月的帖子，默认12个月
- `--threads`: 可选，并发线程数，默认5个线程
- `--fetch-content`: 可选，如果指定此参数，会爬取每个帖子的正文内容（会增加运行时间）
- `--max-pages`: 可选，最大爬取页数，默认1000页
- `--chromedriver-path`: 可选，ChromeDriver的路径，默认使用 `I:\chromedriver-win64\chromedriver.exe`

## 示例

### 示例1：爬取000592近12个月的帖子（不爬取内容）

```bash
python crawl_stock_posts.py --stock-code 000592
```

### 示例2：爬取000592近6个月的帖子，并爬取内容

```bash
python crawl_stock_posts.py --stock-code 000592 --months 6 --fetch-content
```

### 示例3：使用10个线程快速爬取

```bash
python crawl_stock_posts.py --stock-code 000592 --threads 10
```

## 输出文件

脚本会在 `spider/data/` 目录下生成CSV文件，文件名格式为：
```
{股票代码}_posts_{月数}months.csv
```

例如：`000592_posts_12months.csv`

## CSV文件字段说明

- `stockbar_code`: 股票代码
- `stockbar_name`: 股票名称
- `post_id`: 帖子ID
- `post_title`: 帖子标题
- `post_content`: 帖子正文内容（如果使用了 `--fetch-content`）
- `post_comments`: 帖子评论（如果使用了 `--fetch-content`）
- `post_click_count`: 阅读量
- `post_comment_count`: 评论数
- `post_forward_count`: 转发数
- `post_publish_time`: 发布时间
- `post_last_time`: 最后回复时间
- `post_has_pic`: 是否有图片
- `post_has_video`: 是否有视频
- `bullish_bearish`: 看涨看跌
- `post_url`: 帖子URL
- `crawl_time`: 爬取时间

## 注意事项

1. **ChromeDriver路径**: 请确保ChromeDriver路径正确，或者使用 `--chromedriver-path` 参数指定
2. **网络延迟**: 脚本会自动添加随机延迟，避免请求过快被封
3. **时间范围**: 脚本会自动判断帖子时间，超出范围的帖子会被过滤
4. **去重**: 脚本会自动去重，已存在的帖子不会重复爬取
5. **中断恢复**: 如果脚本中断，重新运行时会保留已有数据，只添加新帖子

## 常见问题

### Q: 如何修改ChromeDriver路径？
A: 使用 `--chromedriver-path` 参数，或者直接修改脚本中的 `CHROMEDRIVER_PATH` 默认值。

### Q: 爬取内容很慢怎么办？
A: 如果不关心帖子正文内容，可以不使用 `--fetch-content` 参数，只爬取标题和基本信息会快很多。

### Q: 如何爬取更长时间范围的帖子？
A: 使用 `--months` 参数，例如 `--months 24` 爬取近24个月的帖子。

### Q: 脚本中断后如何继续？
A: 直接重新运行脚本即可，脚本会自动检测已有数据，只添加新帖子。

## 依赖要求

- Python 3.7+
- selenium
- Chrome浏览器
- ChromeDriver（需要与Chrome版本匹配）

## 安装依赖

```bash
pip install selenium
```

## 注意事项

⚠️ **请遵守网站的robots.txt和使用条款，合理使用爬虫，避免对服务器造成过大压力。**

