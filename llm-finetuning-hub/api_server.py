#!/usr/bin/env python3
"""
LLM Fine-tuning Hub API 服务器
提供训练、预测等 API 接口
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import threading
import subprocess
import time
from pathlib import Path
import torch

# 添加 spider 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'spider'))

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 检测 CUDA 是否可用
CUDA_AVAILABLE = torch.cuda.is_available()
DEVICE = "cuda" if CUDA_AVAILABLE else "cpu"
DEVICE_MAP = "cuda" if CUDA_AVAILABLE else None  # CPU 模式不使用 device_map

print(f"🔍 检测到设备: {DEVICE}")
if not CUDA_AVAILABLE:
    print("⚠️  警告: CUDA 不可用，将使用 CPU 模式（训练速度会较慢）")

# 配置
BASE_DIR = Path(__file__).parent
TRAIN_DATA_FILE = BASE_DIR.parent / 'train_sentiment.jsonl'
MODEL_PATH = "I:/models_cache/qwen/Qwen2.5-1.5B-Instruct"
OUTPUT_DIR = BASE_DIR.parent / 'qwen_sentiment_lora'

# 训练状态
training_status = {
    'is_training': False,
    'progress': 0,
    'status': None,  # 'running', 'completed', 'error'
    'message': ''
}

# 训练进程
training_process = None


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'message': 'API server is running'})


@app.route('/api/train/start', methods=['POST'])
def start_training():
    """启动训练"""
    global training_status, training_process
    
    if training_status['is_training']:
        return jsonify({'error': '训练正在进行中'}), 400
    
    try:
        data = request.json
        learning_rate = data.get('learning_rate', 3e-4)
        lora_rank = data.get('lora_rank', 8)
        batch_size = data.get('batch_size', 2)
        gradient_checkpointing = data.get('gradient_checkpointing', True)
        aim_logging = data.get('aim_logging', True)
        
        # 检查训练数据文件
        if not TRAIN_DATA_FILE.exists():
            return jsonify({'error': f'训练数据文件不存在: {TRAIN_DATA_FILE}'}), 400
        
        # 重置状态
        training_status = {
            'is_training': True,
            'progress': 0,
            'status': 'running',
            'message': '训练已启动'
        }
        
        # 在后台线程中启动训练
        def run_training():
            try:
                import torch
                from datasets import load_dataset
                from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, TrainerCallback
                from peft import LoraConfig, get_peft_model, TaskType
                from trl import SFTTrainer
                
                # 在函数内部重新检测 CUDA（确保可以访问）
                cuda_available = torch.cuda.is_available()
                device = "cuda" if cuda_available else "cpu"
                device_map = "cuda" if cuda_available else None
                
                # GPU 诊断信息
                if cuda_available:
                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    print(f"🖥️  GPU: {gpu_name}")
                    print(f"💾 GPU 显存: {gpu_memory:.1f} GB")
                    print(f"📊 当前 GPU 占用: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
                
                # 更新训练状态
                training_status['progress'] = 10
                training_status['message'] = '正在加载模型...'
                
                # 加载模型
                tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
                
                # 根据设备选择 dtype 和 device_map
                if cuda_available:
                    model = AutoModelForCausalLM.from_pretrained(
                        MODEL_PATH,
                        dtype=torch.float16,
                        device_map=device_map,
                        trust_remote_code=True
                    )
                else:
                    # CPU 模式使用 float32
                    model = AutoModelForCausalLM.from_pretrained(
                        MODEL_PATH,
                        torch_dtype=torch.float32,
                        trust_remote_code=True
                    )
                    model = model.to(device)
                
                training_status['progress'] = 30
                training_status['message'] = '正在配置 LoRA...'
                
                # LoRA 配置
                peft_config = LoraConfig(
                    task_type=TaskType.CAUSAL_LM,
                    inference_mode=False,
                    r=lora_rank,
                    lora_alpha=32,
                    lora_dropout=0.1,
                    target_modules=["q_proj", "v_proj"]
                )
                model = get_peft_model(model, peft_config)
                
                # 确保模型在 GPU 上
                if cuda_available:
                    model = model.cuda()
                    print(f"✅ 模型已加载到 GPU")
                    print(f"📊 GPU 显存占用: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
                
                training_status['progress'] = 40
                training_status['message'] = '正在加载数据...'
                
                # 加载数据
                dataset = load_dataset("json", data_files=str(TRAIN_DATA_FILE), split="train")
                
                training_status['progress'] = 50
                training_status['message'] = '开始训练...'
                
                # 根据 GPU 显存动态调整 batch size
                if cuda_available:
                    # 尝试增加 batch size 以提高 GPU 利用率
                    # 1.5B 模型在 8GB 显存上可以支持更大的 batch
                    optimal_batch_size = min(batch_size * 2, 8)  # 最多 8
                    if optimal_batch_size > batch_size:
                        print(f"📈 优化: 将 batch size 从 {batch_size} 增加到 {optimal_batch_size} 以提高 GPU 利用率")
                        batch_size = optimal_batch_size
                
                # 训练参数（根据设备调整）
                args = TrainingArguments(
                    output_dir=str(OUTPUT_DIR),
                    per_device_train_batch_size=batch_size if cuda_available else 1,
                    gradient_accumulation_steps=4 if cuda_available else 16,  # 减少累积步数，增加实际 batch
                    num_train_epochs=5,
                    learning_rate=learning_rate,
                    logging_steps=10,
                    save_strategy="no",
                    fp16=cuda_available,
                    gradient_checkpointing=gradient_checkpointing if cuda_available else False,  # CPU 模式关闭
                    dataloader_num_workers=4 if cuda_available else 0,  # GPU 模式使用多进程加载数据
                    dataloader_pin_memory=True if cuda_available else False,  # GPU 模式固定内存
                    optim="adamw_torch",
                    report_to="aim" if aim_logging else "none",
                    remove_unused_columns=False,  # 保留所有列
                )
                
                # 创建训练器（max_seq_length 在 SFTTrainer 中设置，不在 TrainingArguments 中）
                trainer = SFTTrainer(
                    model=model,
                    args=args,
                    train_dataset=dataset,
                    peft_config=peft_config,
                    max_seq_length=512,  # 限制序列长度，节省显存
                )
                
                # 训练（带进度更新和 GPU 监控）
                class ProgressCallback(TrainerCallback):
                    def on_log(self, args, state, control, logs=None, **kwargs):
                        if state.epoch is not None:
                            epoch = state.epoch
                            training_status['progress'] = 50 + int(epoch * 10)
                            
                            # GPU 使用率信息
                            gpu_info = ""
                            if cuda_available:
                                allocated = torch.cuda.memory_allocated(0) / 1024**3
                                reserved = torch.cuda.memory_reserved(0) / 1024**3
                                gpu_info = f" | GPU: {allocated:.1f}/{reserved:.1f}GB"
                            
                            training_status['message'] = f'训练中... Epoch {epoch:.1f}/5{gpu_info}'
                            
                            # 打印训练日志
                            if logs:
                                loss = logs.get('loss', 'N/A')
                                print(f"Epoch {epoch:.2f} | Loss: {loss}{gpu_info}")
                
                trainer.add_callback(ProgressCallback())
                
                training_status['progress'] = 60
                
                # 训练前打印配置
                print("\n" + "="*60)
                print("🚀 开始训练")
                print("="*60)
                print(f"设备: {device}")
                print(f"Batch Size: {batch_size}")
                print(f"Gradient Accumulation: {args.gradient_accumulation_steps}")
                print(f"有效 Batch Size: {batch_size * args.gradient_accumulation_steps}")
                print(f"FP16: {cuda_available}")
                print(f"Gradient Checkpointing: {gradient_checkpointing}")
                print(f"DataLoader Workers: {args.dataloader_num_workers}")
                print("="*60 + "\n")
                
                trainer.train()
                
                training_status['progress'] = 90
                training_status['message'] = '正在保存模型...'
                
                # 保存模型
                trainer.model.save_pretrained(str(OUTPUT_DIR))
                tokenizer.save_pretrained(str(OUTPUT_DIR))
                
                training_status['progress'] = 100
                training_status['status'] = 'completed'
                training_status['message'] = '训练完成！'
                training_status['is_training'] = False
                
            except Exception as e:
                training_status['status'] = 'error'
                training_status['message'] = f'训练失败: {str(e)}'
                training_status['is_training'] = False
                import traceback
                traceback.print_exc()
        
        # 启动训练线程
        thread = threading.Thread(target=run_training, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': '训练已启动',
            'status': training_status
        })
        
    except Exception as e:
        training_status['is_training'] = False
        training_status['status'] = 'error'
        training_status['message'] = str(e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/train/status', methods=['GET'])
def get_training_status():
    """获取训练状态"""
    status = training_status.copy()
    
    # 添加 GPU 信息
    if CUDA_AVAILABLE:
        try:
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            utilization = (allocated / total) * 100 if total > 0 else 0
            
            status['gpu_info'] = {
                'device_name': torch.cuda.get_device_name(0),
                'memory_allocated_gb': round(allocated, 2),
                'memory_reserved_gb': round(reserved, 2),
                'memory_total_gb': round(total, 2),
                'memory_utilization_percent': round(utilization, 1),
            }
        except Exception as e:
            status['gpu_info'] = {'error': str(e)}
    else:
        status['gpu_info'] = {'available': False}
    
    return jsonify(status)


@app.route('/api/predict', methods=['POST'])
def predict():
    """模型预测"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        use_finetuned = data.get('use_finetuned', False)
        
        if not prompt:
            return jsonify({'error': 'prompt 不能为空'}), 400
        
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        
        # 加载模型
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        
        # 根据设备选择加载方式
        if CUDA_AVAILABLE:
            base_model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                dtype=torch.float16,
                device_map=DEVICE_MAP,
                trust_remote_code=True
            )
        else:
            base_model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                torch_dtype=torch.float32,
                trust_remote_code=True
            )
            base_model = base_model.to(DEVICE)
        
        # 如果使用微调模型，加载 LoRA
        if use_finetuned and OUTPUT_DIR.exists():
            model = PeftModel.from_pretrained(base_model, str(OUTPUT_DIR))
            system_prompt = "判断股票评论情绪。P=看多, N=看空, O=中性。"
        else:
            model = base_model
            system_prompt = "文本：\"{text}\"\n\n请判断上述金融文本的情绪。\n规则：1.客观陈述(财报/公告)选O。2.利空风险选N。3.利好机会选P。\n请输出一个字母(P/N/O)："
        
        model.eval()
        
        # 构造消息
        if use_finetuned:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            text = system_prompt.format(text=prompt)
        
        # 推理
        inputs = tokenizer([text], return_tensors="pt")
        if CUDA_AVAILABLE:
            inputs = inputs.to(model.device)
        else:
            inputs = inputs.to(DEVICE)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=2,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        
        # 解码
        generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
        response = generated.split(text)[-1].strip() if text in generated else generated
        
        # 清理输出
        response = response.strip().upper()
        if response in ["P", "N", "O"]:
            result = response
        else:
            import re
            match = re.search(r'\b([PNO])\b', response)
            result = match.group(1) if match else "O"
        
        return jsonify({
            'success': True,
            'response': result,
            'full_response': response
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/validate', methods=['POST'])
def validate_data():
    """验证 JSONL 数据"""
    try:
        data = request.json
        jsonl_text = data.get('data', '')
        
        if not jsonl_text.strip():
            return jsonify({
                'valid': False,
                'message': '数据为空',
                'errors': []
            })
        
        lines = jsonl_text.strip().split('\n')
        errors = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                parsed = json.loads(line)
                if not isinstance(parsed, dict):
                    errors.append(f'第 {i} 行: 不是有效的 JSON 对象')
                elif 'messages' not in parsed:
                    errors.append(f'第 {i} 行: 缺少 messages 字段')
                elif not isinstance(parsed['messages'], list):
                    errors.append(f'第 {i} 行: messages 必须是数组')
            except json.JSONDecodeError as e:
                errors.append(f'第 {i} 行: JSON 格式错误 - {str(e)}')
        
        if errors:
            return jsonify({
                'valid': False,
                'message': f'发现 {len(errors)} 个错误',
                'errors': errors[:10]  # 只返回前10个错误
            })
        else:
            return jsonify({
                'valid': True,
                'message': f'验证通过！共 {len(lines)} 条有效记录',
                'count': len(lines)
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/data/clean', methods=['POST'])
def clean_data():
    """清理数据"""
    try:
        data = request.json
        jsonl_text = data.get('data', '')
        
        # 清理数据
        cleaned = jsonl_text
        # 移除多余空格
        cleaned = ' '.join(cleaned.split())
        # 移除特殊控制字符（保留换行符）
        import re
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', cleaned)
        # 清理行尾空格
        lines = cleaned.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        cleaned = '\n'.join(cleaned_lines)
        
        return jsonify({
            'success': True,
            'cleaned_data': cleaned,
            'original_length': len(jsonl_text),
            'cleaned_length': len(cleaned)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('🚀 启动 LLM Fine-tuning Hub API 服务器...')
    print(f'📊 服务地址: http://localhost:5001')
    print(f'🖥️  运行设备: {DEVICE.upper()}')
    if not CUDA_AVAILABLE:
        print('⚠️  注意: 当前使用 CPU 模式，训练速度会较慢')
    print(f'📈 API 端点:')
    print(f'   GET  /api/health              - 健康检查')
    print(f'   POST /api/train/start         - 启动训练')
    print(f'   GET  /api/train/status         - 获取训练状态')
    print(f'   POST /api/predict              - 模型预测')
    print(f'   POST /api/data/validate       - 验证数据')
    print(f'   POST /api/data/clean           - 清理数据')
    print('\n按 Ctrl+C 停止服务')
    
    app.run(host='0.0.0.0', port=5001, debug=True)

