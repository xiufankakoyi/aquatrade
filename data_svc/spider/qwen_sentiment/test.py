import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import json
import time
import os
from tqdm import tqdm

# ================= 配置区域 =================
BASE_MODEL_PATH = "I:/models_cache/qwen/Qwen2.5-1.5B-Instruct"
LORA_PATH = "./qwen_sentiment_lora"  # LoRA模型路径（相对于当前文件夹）
TEST_DATA_FILE = "../test_data.json"  # 测试数据文件（在上级目录）
# ===========================================

# v10 Prompt 配置 (基座模型的最佳表现)
V10_TEMPLATE = "文本：\"{text}\"\n\n请判断上述金融文本的情绪。\n规则：1.客观陈述(财报/公告)选O。2.利空风险选N。3.利好机会选P。\n请输出一个字母(P/N/O)："

# LoRA Prompt 配置 (训练时的极简指令)
LORA_SYSTEM = "判断股票评论情绪。P=看多, N=看空, O=中性。"
# ===========================================

def load_data():
    if not os.path.exists(TEST_DATA_FILE):
        print(f"❌ 找不到测试数据: {TEST_DATA_FILE}")
        return []
    with open(TEST_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_output(text):
    """提取 P/N/O，处理可能的废话"""
    text = text.strip().upper()
    # 优先找单独的字母
    if text in ["P", "N", "O"]:
        return text
    # 找包含的字母
    import re
    match = re.search(r'\b([PNO])\b', text)
    if match: return match.group(1)
    # 兜底
    for char in text:
        if char in ["P", "N", "O"]: return char
    return "O" # 无法识别归为中性

def run_base_inference(model, tokenizer, data):
    """运行 v10 Prompt (基座模型)"""
    print("\n🔵 [第一回合] 基座模型 + v10 Prompt 正在推理...")
    results = []
    
    # 构造 Prompts
    prompts = [V10_TEMPLATE.format(text=item['text']) for item in data]
    
    # 批量推理 (Batch Inference) 加速
    batch_size = 8
    for i in tqdm(range(0, len(prompts), batch_size), desc="Base Model"):
        batch_prompts = prompts[i:i+batch_size]
        inputs = tokenizer(batch_prompts, return_tensors="pt", padding=True, truncation=True).to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs, 
                max_new_tokens=2, 
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
            
        # 解码
        for j, output in enumerate(outputs):
            # 跳过 input 部分
            input_len = inputs.input_ids[j].shape[0]
            # 注意：generate 输出包含了 input，需要切片。
            # 但 batch生成时 padding 可能会干扰，最稳妥是用 batch_decode 后处理
            pass 
        
        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        
        # 提取结果 (需要去掉 Prompt 部分)
        for j, text in enumerate(decoded):
            # 简单粗暴：取最后几个字符清洗，因为 v10 把指令放在最后
            # 或者更精准：去掉 prompt 长度
            # 这里为了稳健，直接取 generated 的最后部分
            full_prompt = batch_prompts[j]
            response = text[len(full_prompt):]
            results.append(clean_output(response))
            
    return results

def run_lora_inference(base_model, tokenizer, data):
    """加载 LoRA 并推理"""
    print("\n🔴 [第二回合] 加载 LoRA 补丁...")
    try:
        model = PeftModel.from_pretrained(base_model, LORA_PATH)
        model.eval()
        print("✅ LoRA 加载成功！变身完成！")
    except Exception as e:
        print(f"❌ LoRA 加载失败: {e}")
        return []

    print("🔴 [第二回合] LoRA 微调模型 正在推理...")
    results = []
    
    # LoRA 训练时用的是 Chat 模板，这里必须保持一致
    # 构造 Chat Messages
    chat_prompts = []
    for item in data:
        messages = [
            {"role": "system", "content": LORA_SYSTEM},
            {"role": "user", "content": item['text']}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        chat_prompts.append(text)
    
    batch_size = 8
    for i in tqdm(range(0, len(chat_prompts), batch_size), desc="LoRA Model"):
        batch_texts = chat_prompts[i:i+batch_size]
        inputs = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True).to(model.device)
        
        with torch.no_grad():
            # LoRA 只需要生成 1 个 token
            outputs = model.generate(
                **inputs, 
                max_new_tokens=1, 
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
            
        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        
        for j, text in enumerate(decoded):
            # 提取 assistant 的回复
            # Qwen 的 chat template 通常以 "assistant\n" 结尾
            # 我们直接找 user input 之后的内容
            user_input = data[i+j]['text']
            # 简单的分割逻辑
            parts = text.split(user_input)
            if len(parts) > 1:
                response = parts[-1].strip()
            else:
                response = text
            results.append(clean_output(response))
            
    return results

def main():
    # 1. 加载数据
    data = load_data()
    if not data: return
    print(f"📊 测试数据集大小: {len(data)} 条")
    
    # 准备标签
    refs = []
    for item in data:
        r = item['ref']
        if isinstance(r, list): r = r[0]
        if "Pos" in r: refs.append("P")
        elif "Neg" in r: refs.append("N")
        else: refs.append("O")

    # 2. 加载基座模型
    print("🚀 正在加载基座模型 (Qwen2.5-1.5B)...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token
    
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH, 
        torch_dtype=torch.float16, 
        device_map="cuda",
        trust_remote_code=True
    )

    # 3. 跑 v10 (Baseline)
    t0 = time.time()
    v10_preds = run_base_inference(base_model, tokenizer, data)
    v10_time = time.time() - t0

    # 4. 跑 LoRA (Challenger)
    # 注意：PeftModel 会直接修改 base_model 的结构
    t0 = time.time()
    lora_preds = run_lora_inference(base_model, tokenizer, data)
    lora_time = time.time() - t0

    # 5. 计算得分
    def calc_score(preds, targets):
        correct = sum(1 for p, t in zip(preds, targets) if p == t)
        return correct, correct / len(targets) * 100

    v10_correct, v10_acc = calc_score(v10_preds, refs)
    lora_correct, lora_acc = calc_score(lora_preds, refs)

    # 6. 输出战报
    print("\n" + "="*60)
    print("⚔️  终极决战：Prompt工程 vs 微调模型  ⚔️")
    print("="*60)
    print(f"{'选手':<15} | {'准确率':<10} | {'答对数':<8} | {'总耗时':<8}")
    print("-" * 60)
    print(f"{'v10 Prompt':<15} | {v10_acc:>6.1f}%    | {v10_correct}/{len(data)}    | {v10_time:.2f}s")
    print(f"{'LoRA Fine-tune':<15} | {lora_acc:>6.1f}%    | {lora_correct}/{len(data)}    | {lora_time:.2f}s")
    print("-" * 60)

    if lora_acc > v10_acc:
        print(f"🏆 胜者: LoRA 微调模型! (提升了 {lora_acc - v10_acc:.1f}%)")
    elif lora_acc < v10_acc:
        print(f"🏆 胜者: v10 Prompt! (微调可能过拟合或数据量不足)")
    else:
        print("🤝 平局！")

    # 7. 详细错题分析
    print("\n🔍 差异分析 (LoRA 修正了哪些 v10 的错误?)")
    print("-" * 60)
    fixed_count = 0
    broken_count = 0
    
    for i, (v10, lora, ref, item) in enumerate(zip(v10_preds, lora_preds, refs, data)):
        if v10 != ref and lora == ref:
            print(f"✅ LoRA 修正 [#{i+1}]: {item['text']}")
            print(f"   v10: {v10} -> LoRA: {lora} (正解: {ref})")
            fixed_count += 1
        elif v10 == ref and lora != ref:
            print(f"❌ LoRA 改错 [#{i+1}]: {item['text']}")
            print(f"   v10: {v10} -> LoRA: {lora} (正解: {ref})")
            broken_count += 1
            
    print(f"\n总结: LoRA 修正了 {fixed_count} 个错误，但引入了 {broken_count} 个新错误。")

if __name__ == "__main__":
    main()

