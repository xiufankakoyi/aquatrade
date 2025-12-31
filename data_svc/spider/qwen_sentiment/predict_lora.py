import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import time

# ================= 配置 =================
BASE_MODEL_PATH = "I:/models_cache/qwen/Qwen2.5-1.5B-Instruct"
LORA_PATH = "./qwen_sentiment_lora"  # LoRA模型路径（相对于当前文件夹）
# =======================================

def get_lora_model():
    print("正在加载基座模型...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH, 
        dtype=torch.float16,  # 使用 dtype 替代已弃用的 torch_dtype
        device_map="cuda"
    )
    
    print("正在加载 LoRA 权重...")
    # 这一步是关键：把微调好的"补丁"打上去
    model = PeftModel.from_pretrained(base_model, LORA_PATH)
    model.eval()
    return tokenizer, model

def predict_one(text, tokenizer, model):
    # 必须和训练时的 Prompt 保持一致
    messages = [
        {"role": "system", "content": "判断股票评论情绪。P=看多, N=看空, O=中性。"},
        {"role": "user", "content": text}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    t0 = time.time()
    with torch.no_grad():
        # max_new_tokens=1 即可，因为我们要的就是一个字母
        outputs = model.generate(**inputs, max_new_tokens=2, do_sample=False)
    t1 = time.time()
    
    # 提取结果
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Qwen 的 chat 模板可能会把输入也带出来，我们只取最后生成的
    response = generated.split(text)[-1].strip() # 简单的提取逻辑
    
    # 只要微调成功，它大概率只会输出 "P", "N", 或 "O"
    return response, (t1 - t0) * 1000

if __name__ == "__main__":
    tokenizer, model = get_lora_model()
    
    # 随便测几个
    test_cases = [
        "回调就是加仓机会",
        "公司造假实锤了",
        "今天收盘价15.3元",
        "散户恐慌我贪婪",
        "利好兑现，该跑了"
    ]
    
    print("\n=== 微调模型测试 ===")
    for text in test_cases:
        res, ms = predict_one(text, tokenizer, model)
        print(f"文本: {text[:10]}... -> 预测: {res} ({ms:.1f}ms)")

