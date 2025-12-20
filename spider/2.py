import torch
from transformers import pipeline, AutoTokenizer, AutoModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

class ModelCompetition:
    def __init__(self):
        self.device = 0 if torch.cuda.is_available() else -1
        self.device_str = "cuda" if torch.cuda.is_available() else "cpu"
        
        # === 四个参赛模型配置 ===
        self.models_config = [
            {
                "name": "RoBERTa-wwm", 
                "path": "hfl/chinese-roberta-wwm-ext", 
                "type": "fill-mask"
            },
            {
                "name": "MacBERT", 
                "path": "hfl/chinese-macbert-base", 
                "type": "fill-mask"
            },
            {
                "name": "BERT-wwm", 
                "path": "hfl/chinese-bert-wwm", 
                "type": "fill-mask"
            },
            {
                "name": "BGE-large-zh",
                "path": "BAAI/bge-large-zh-v1.5",
                "type": "embedding"
            }
        ]
        
        self.pipelines = []
        self.embedding_model = None
        self.embedding_tokenizer = None
        self.load_models()
        
        self.pos_token = "涨"
        self.neg_token = "跌"
        
        # BGE 模型的参考文本（用于相似度计算）
        self.pos_reference = "股价会上涨，后市看涨，趋势向上"
        self.neg_reference = "股价会下跌，后市看跌，趋势向下"

    def load_models(self):
        print(f"🚀 初始化四个模型参赛系统...")
        
        # 加载所有模型
        for cfg in self.models_config:
            try:
                print(f"  🔄 加载 {cfg['name']}...", end="")
                if cfg['type'] == 'fill-mask':
                    pipe = pipeline('fill-mask', model=cfg['path'], device=self.device)
                    self.pipelines.append({
                        "pipe": pipe,
                        "name": cfg['name'],
                        "type": "fill-mask"
                    })
                elif cfg['type'] == 'embedding':
                    self.embedding_tokenizer = AutoTokenizer.from_pretrained(cfg['path'])
                    self.embedding_model = AutoModel.from_pretrained(cfg['path'])
                    self.embedding_model.to(self.device_str)
                    self.embedding_model.eval()
                    self.pipelines.append({
                        "name": cfg['name'],
                        "type": "embedding"
                    })
                print(" ✅")
            except Exception as e:
                print(f" ❌ 失败 ({e})")
        
        if len(self.pipelines) == 0:
            raise ValueError("❌ 没有任何模型加载成功，无法运行！")
        
        print(f"✅ 成功加载 {len(self.pipelines)} 个模型，准备比赛！\n")
    
    def _encode_texts(self, texts):
        """使用 BGE 模型编码文本列表，返回嵌入向量"""
        if self.embedding_model is None:
            return None
        
        with torch.no_grad():
            encoded_input = self.embedding_tokenizer(
                texts, 
                padding=True, 
                truncation=True, 
                max_length=512,
                return_tensors='pt'
            ).to(self.device_str)
            
            model_output = self.embedding_model(**encoded_input)
            # BGE 模型使用 [CLS] token 的嵌入，并进行归一化
            embeddings = model_output[0][:, 0]  # [batch_size, hidden_size]
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return embeddings.cpu().numpy()

    def _analyze_single_model(self, model_item, texts, batch_size=32):
        """单个模型独立分析"""
        if not texts: return []
        
        n_samples = len(texts)
        results = []
        
        if model_item['type'] == 'fill-mask':
            # Fill-Mask 模型分析
            pipe = model_item['pipe']
            masked_texts = [f"股民评论「{t}」，这意味着股价后市会{pipe.tokenizer.mask_token}。" for t in texts]
            
            try:
                pipe_results = pipe(masked_texts, batch_size=batch_size)
                
                for idx, res_list in enumerate(pipe_results):
                    p_up = 0.0
                    p_down = 0.0
                    
                    for res in res_list:
                        token = res['token_str'].replace(" ", "")
                        if token == self.pos_token:
                            p_up = res['score']
                        elif token == self.neg_token:
                            p_down = res['score']
                    
                    prob_diff = p_up - p_down
                    label = 0
                    if prob_diff > 0.03:
                        label = 1
                    elif prob_diff < -0.03:
                        label = -1
                    
                    results.append({
                        "label": label,
                        "prob_up": p_up,
                        "prob_down": p_down,
                        "diff": prob_diff
                    })
            except Exception as e:
                print(f"⚠️ 模型 {model_item['name']} 推理失败: {e}")
                return None
                
        elif model_item['type'] == 'embedding':
            # BGE 嵌入模型分析
            if self.embedding_model is None:
                return None
            
            try:
                text_embeddings = self._encode_texts(texts)
                pos_emb = self._encode_texts([self.pos_reference])[0]
                neg_emb = self._encode_texts([self.neg_reference])[0]
                
                pos_similarities = cosine_similarity(text_embeddings, pos_emb.reshape(1, -1)).flatten()
                neg_similarities = cosine_similarity(text_embeddings, neg_emb.reshape(1, -1)).flatten()
                
                # 归一化相似度为概率
                pos_probs = (pos_similarities + 1) / 2
                neg_probs = (neg_similarities + 1) / 2
                total_probs = pos_probs + neg_probs
                pos_probs = pos_probs / (total_probs + 1e-8)
                neg_probs = neg_probs / (total_probs + 1e-8)
                
                for idx in range(n_samples):
                    prob_diff = pos_probs[idx] - neg_probs[idx]
                    label = 0
                    if prob_diff > 0.03:
                        label = 1
                    elif prob_diff < -0.03:
                        label = -1
                    
                    results.append({
                        "label": label,
                        "prob_up": pos_probs[idx],
                        "prob_down": neg_probs[idx],
                        "diff": prob_diff
                    })
            except Exception as e:
                print(f"⚠️ 模型 {model_item['name']} 推理失败: {e}")
                return None
        
        return results
    
    def compete(self, texts, true_labels, batch_size=32):
        """
        四个模型比赛，返回每个模型的准确率
        
        Args:
            texts: 测试文本列表
            true_labels: 真实标签列表 (1=看涨, -1=看跌, 0=中性)
            batch_size: 批处理大小
        """
        print("=" * 80)
        print("🏆 四个模型准确率比赛开始！")
        print("=" * 80)
        
        model_results = {}
        
        # 每个模型独立分析
        for model_item in self.pipelines:
            model_name = model_item['name']
            print(f"\n📊 {model_name} 正在分析 {len(texts)} 条文本...")
            
            predictions = self._analyze_single_model(model_item, texts, batch_size)
            
            if predictions is None:
                print(f"  ❌ {model_name} 分析失败，跳过")
                continue
            
            # 提取预测标签
            pred_labels = [p['label'] for p in predictions]
            
            # 计算准确率指标
            accuracy = accuracy_score(true_labels, pred_labels)
            
            # 计算精确率、召回率、F1（只考虑非中性样本）
            non_neutral_mask = np.array(true_labels) != 0
            if non_neutral_mask.sum() > 0:
                y_true_binary = np.array(true_labels)[non_neutral_mask]
                y_pred_binary = np.array(pred_labels)[non_neutral_mask]
                # 转换为二分类（1 vs -1）
                y_true_binary = (y_true_binary > 0).astype(int)
                y_pred_binary = (y_pred_binary > 0).astype(int)
                
                precision = precision_score(y_true_binary, y_pred_binary, average='binary', zero_division=0)
                recall = recall_score(y_true_binary, y_pred_binary, average='binary', zero_division=0)
                f1 = f1_score(y_true_binary, y_pred_binary, average='binary', zero_division=0)
            else:
                precision = recall = f1 = 0.0
            
            # 混淆矩阵
            cm = confusion_matrix(true_labels, pred_labels, labels=[-1, 0, 1])
            
            model_results[model_name] = {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "predictions": pred_labels,
                "confusion_matrix": cm
            }
            
            print(f"  ✅ {model_name} 分析完成")
            print(f"     准确率: {accuracy:.4f} ({accuracy*100:.2f}%)")
            print(f"     精确率: {precision:.4f}")
            print(f"     召回率: {recall:.4f}")
            print(f"     F1分数: {f1:.4f}")
        
        # 排名
        print("\n" + "=" * 80)
        print("🏆 比赛结果排名（按准确率）")
        print("=" * 80)
        
        sorted_models = sorted(model_results.items(), key=lambda x: x[1]['accuracy'], reverse=True)
        
        for rank, (model_name, metrics) in enumerate(sorted_models, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            print(f"{medal} 第{rank}名: {model_name}")
            print(f"   准确率: {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
            print(f"   精确率: {metrics['precision']:.4f} | 召回率: {metrics['recall']:.4f} | F1: {metrics['f1']:.4f}")
            print(f"   混淆矩阵:")
            print(f"   {metrics['confusion_matrix']}")
            print()
        
        return model_results

# ==========================================
# 🧪 测试 Demo：四个模型比赛
# ==========================================
if __name__ == "__main__":
    analyzer = ModelCompetition()
    
    # 测试数据集（文本 + 真实标签）
    # 标签: 1=看涨, -1=看跌, 0=中性
    test_data = [
        # 看涨样本 (label=1)
        ("量价齐升，趋势走出来了", 1),
        ("主力回来了，这位置安全", 1),
        ("洗盘而已，别被吓跑", 1),
        ("这波不翻倍对不起庄家", 1),
        ("资金开始说话了", 1),
        ("底部放量，懂的都懂", 1),
        ("趋势不破，继续拿", 1),
        ("北向连续加仓", 1),
        ("这种走势明显有预期差", 1),
        ("不买真的后悔", 1),
        ("现在不上车就晚了", 1),
        ("最后一次上车机会", 1),
        ("已经没有下跌空间了", 1),
        ("再跌我吃键盘", 1),
        ("错过这波就是一年", 1),
        
        # 看跌样本 (label=-1)
        ("完了，又站岗", -1),
        ("这票已经废了", -1),
        ("每天一个新低，服了", -1),
        ("主力跑路了还不信", -1),
        ("拉高出货太明显", -1),
        ("不割不行了", -1),
        ("这走势一看就是骗炮", -1),
        ("再买就是送钱", -1),
        ("庄家吃相太难看", -1),
        ("关灯吃面", -1),
        ("埋了", -1),
        ("被套在山顶", -1),
        ("抬走，下一个", -1),
        ("割肉止损", -1),
        ("韭菜集合地", -1),
        ("这走势真漂亮，一路向下", -1),
        ("每天跌一点，细水长流", -1),
        ("稳得很，稳稳地亏", -1),
        ("这不是下跌，是自由落体", -1),
        ("利好出来反而跌，老套路了", -1),
        
        # 中性样本 (label=0)
        ("感觉不太对，但又说不上来", 0),
        ("总觉得后面有戏", 0),
        ("这票有点东西", 0),
        ("说不清楚，反正不敢买", 0),
        ("看着像要拉，又不像", 0),
        ("应该快了吧", 0),
        ("主力明显在等散户走", 0),
        ("看看再说", 0),
        ("路过", 0),
        ("坐等收盘", 0),
        ("今天人不多啊", 0),
        ("评论区真热闹", 0),
        ("不懂这个票", 0),
        ("说是利好，怎么一点反应没有", 0),
        ("不涨我认了，别天天阴跌", 0),
        ("被套了，但感觉还能救", 0),
        ("割了又怕它涨", 0),
        ("拿着难受，卖了更难受", 0),
        ("这位置不涨才奇怪", 0),
        ("涨不动也不至于跌成这样", 0),
        ("说洗盘吧，有点狠", 0),
        ("说出货吧，又不像", 0),
        ("反正散户永远是最后知道的", 0),
    ]
    
    # 分离文本和标签
    test_texts = [item[0] for item in test_data]
    true_labels = [item[1] for item in test_data]
    
    # 开始比赛
    results = analyzer.compete(test_texts, true_labels, batch_size=8)
    
    print("\n" + "=" * 80)
    print("📋 详细预测对比（前10条）")
    print("=" * 80)
    
    for i in range(min(10, len(test_texts))):
        print(f"\n文本 {i+1}: 【{test_texts[i]}】")
        print(f"真实标签: {'🔴 看涨' if true_labels[i] == 1 else '🟢 看跌' if true_labels[i] == -1 else '⚪ 中性'}")
        print("各模型预测:")
        for model_name, metrics in results.items():
            pred = metrics['predictions'][i]
            pred_str = '🔴 看涨' if pred == 1 else '🟢 看跌' if pred == -1 else '⚪ 中性'
            correct = "✅" if pred == true_labels[i] else "❌"
            print(f"  {model_name:15s}: {pred_str} {correct}")