import pandas as pd
import torch
from modelscope import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm
import json
import re
from pathlib import Path
import os

# ================= 配置区域 =================
MODEL_NAME = "qwen/Qwen2.5-1.5B-Instruct" 
BATCH_SIZE = 64 # 如果显存爆了(OOM)，请把这个数字改成 16 或 8
INPUT_DIR = Path("spider/data/new")
MODEL_CACHE_DIR = "I:/models_cache"  # 保持和你刚才下载的一致
# ===========================================

def load_model():
    # 自动创建目录
    if not os.path.exists(MODEL_CACHE_DIR):
        os.makedirs(MODEL_CACHE_DIR)
        
    print(f"🚀 正在加载模型: {MODEL_NAME} ...")
    
    # 因为你已经下载完了，这里会瞬间完成
    model_dir = snapshot_download(MODEL_NAME, cache_dir=MODEL_CACHE_DIR)
    
    tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    
    # === 关键修复 1: 正确设置 padding 属性 ===
    tokenizer.padding_side = "left"  # 设为左填充，适合生成任务
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token # 防止没有 pad_token 报错

    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        device_map="auto",
        torch_dtype=torch.float16,
        trust_remote_code=True
    )
    return tokenizer, model

def make_prompt(text):
    return f"""
分析以下股吧评论的情绪。
规则：
1. Negative: 跌停、吃面、被套、垃圾、崩盘、绿、利空、出货、骗子、核按钮、甚至没绿。
2. Positive: 涨停、吃肉、起飞、利好、满仓、红、大阳线、龙头、板、舒服。
3. Neutral: 纯询问、无意义、新闻陈述。

评论内容："{text}"

请直接输出 JSON，格式：{{"label": "Positive/Neutral/Negative", "score": 0.9, "reason": "理由"}}
"""

def extract_json(response_text):
    try:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    if "Positive" in response_text: return {"label": "Positive", "score": 0.9}
    if "Negative" in response_text: return {"label": "Negative", "score": 0.9}
    return {"label": "Neutral", "score": 0.5}

def process_file(csv_path, tokenizer, model):
    print(f"\n📂 处理文件: {csv_path.name}")
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception as e:
        print(f"❌ 读取错误: {e}")
        return
    
    if 'post_title' not in df.columns: return
    texts = df['post_title'].fillna("").astype(str).tolist()
    
    results_map = {} 

    # === GPU 推理循环 ===
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="🔥 GPU 全速计算中"):
        batch_texts = texts[i : i + BATCH_SIZE]
        batch_indices = range(i, min(i + BATCH_SIZE, len(texts)))
        
        prompts = []
        for text in batch_texts:
            messages = [
                {"role": "system", "content": "你是一个专业的金融情绪分析师。"},
                {"role": "user", "content": make_prompt(text)}
            ]
            text_prompt = tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            prompts.append(text_prompt)
            
        # === 关键修复 2: 移除错误的参数 ===
        inputs = tokenizer(prompts, return_tensors="pt", padding=True).to("cuda")
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs, 
                max_new_tokens=64, 
                temperature=0.1,   
                top_p=0.9,          # 加上这个防止警告
                do_sample=True      # <--- 改为 True，消除冲突警告  
            )
            
        input_len = inputs.input_ids.shape[1]
        generated_ids = outputs[:, input_len:]
        decoded_output = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
        
        for idx, raw_res in zip(batch_indices, decoded_output):
            res_json = extract_json(raw_res)
            results_map[idx] = res_json

    print("💾 正在保存结果...")
    if 'sentiment_label' not in df.columns:
        df['sentiment_label'] = None
        df['sentiment_score'] = None
        df['llm_reason'] = None
        
    for idx, res in results_map.items():
        df.at[idx, 'sentiment_label'] = res.get('label', 'Neutral')
        df.at[idx, 'sentiment_score'] = res.get('score', 0.5)
        df.at[idx, 'llm_reason'] = res.get('reason', '')
        
    output_path = csv_path.parent / (csv_path.stem + "_gpu.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"✅ 完成！已保存为 {output_path.name}")

def main():
    if not torch.cuda.is_available():
        print("❌ 未检测到 GPU！")
        return
        
    print(f"✅ 检测到显卡: {torch.cuda.get_device_name(0)}")
    tokenizer, model = load_model()
    
    if not INPUT_DIR.exists():
        print("目录不存在")
        return

    for f in INPUT_DIR.glob("*.csv"):
        if "_gpu" in f.name: continue
        process_file(f, tokenizer, model)

if __name__ == "__main__":
    main()




