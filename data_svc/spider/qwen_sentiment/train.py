import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    TrainingArguments,
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, TaskType
from trl import SFTTrainer

# ================= 配置 =================
MODEL_PATH = "I:/models_cache/qwen/Qwen2.5-1.5B-Instruct" # 你的模型路径
OUTPUT_DIR = "./qwen_sentiment_lora"  # LoRA模型输出目录（相对于当前文件夹）
DATA_FILE = "train_sentiment.jsonl"   # 训练数据文件（相对于当前文件夹）
# =======================================

def train():
    print("🚀 开始加载模型...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    # 1.5B 模型很小，直接半精度加载即可，不需要量化，速度最快
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, 
        dtype=torch.float16,  # 使用 dtype 替代已弃用的 torch_dtype
        device_map="cuda",
        trust_remote_code=True
    )
    
    # LoRA 配置
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM, 
        inference_mode=False, 
        r=8,            # 秩，越大参数越多
        lora_alpha=32, 
        lora_dropout=0.1,
        target_modules=["q_proj", "v_proj"] # 微调核心注意力层
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 加载数据
    dataset = load_dataset("json", data_files=DATA_FILE, split="train")

    # 训练参数 (针对 8GB 显存优化)
    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,  # 8GB显存：降低batch size避免OOM
        gradient_accumulation_steps=8,  # 增加累积步数保持有效batch size=16
        num_train_epochs=5,             # 数据量少，跑3-5轮即可
        learning_rate=3e-4,              # LoRA 经典学习率
        logging_steps=10,
        save_strategy="no",              # 赶时间，最后保存一次就行
        fp16=True,                       # 开启混合精度加速，节省显存
        gradient_checkpointing=True,     # 开启梯度检查点，用时间换显存
        max_seq_length=512,              # 限制序列长度，节省显存
        dataloader_num_workers=0,        # 8GB显存：设为0避免额外内存占用
        optim="adamw_torch",             # 使用标准AdamW（8bit优化器可能不稳定）
        report_to="none"
    )

    # 这里的 dataset text_field 处理稍微 tricky，直接用 trl 的 SFTTrainer 最简单
    # SFTTrainer 会自动处理 Chat 格式
    # 注意：新版本的 SFTTrainer 不需要单独传递 tokenizer，它会从模型中自动获取
    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset,
        peft_config=peft_config,
    )

    print("🔥 开始训练 (预计耗时 2-5 分钟)...")
    trainer.train()
    
    print(f"💾 保存模型到 {OUTPUT_DIR}...")
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("✅ 微调完成！")

if __name__ == "__main__":
    train()

