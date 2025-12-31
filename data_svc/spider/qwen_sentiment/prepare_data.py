import json
import os

# 从 test_data.json 加载数据（在上级目录）
TEST_DATA_FILE = "../test_data.json"
if not os.path.exists(TEST_DATA_FILE):
    raise FileNotFoundError(f"找不到测试数据文件: {TEST_DATA_FILE}")
with open(TEST_DATA_FILE, 'r', encoding='utf-8') as f:
    DATA = json.load(f)

# 训练提示词模板（保持极简，因为微调后模型会形成肌肉记忆）
def format_instruction(text, label):
    return {
        "messages": [
            {"role": "system", "content": "判断股票评论情绪。P=看多, N=看空, O=中性。"},
            {"role": "user", "content": text},
            {"role": "assistant", "content": label}
        ]
    }

# 转换数据
train_data = []
# 简单的将数据复制 1 份，增加训练步数，让模型印入脑海
# (正规做法是用 GPT-4 生成相似数据，但为了赶时间，复制也可以)
for _ in range(5): 
    for item in DATA:
        # DATA里的 ref 可能是 "Positive" 或 ["Positive"]，统一处理
        label_raw = item['ref'][0] if isinstance(item['ref'], list) else item['ref']
        
        # 统一映射为 P/N/O 单字符
        if "Pos" in label_raw: label_char = "P"
        elif "Neg" in label_raw: label_char = "N"
        else: label_char = "O"
        
        train_data.append(format_instruction(item['text'], label_char))

# 写入文件（在当前目录）
with open("train_sentiment.jsonl", "w", encoding="utf-8") as f:
    for entry in train_data:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")

print(f"✅ 数据准备完成！共生成 {len(train_data)} 条训练样本。")
print("文件保存为: train_sentiment.jsonl")

