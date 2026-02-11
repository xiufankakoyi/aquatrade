# core/research_note.py
"""
研究笔记系统
用于记录实验假设、实验设计、结果分析，并自动关联 Git 版本和回测 ID。
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logger import get_logger

logger = get_logger(__name__)

class ResearchNote:
    """
    结构化研究记录类
    """
    
    def __init__(self, note_dir: str = "data/research_notes"):
        self.note_dir = Path(note_dir)
        self.note_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata = {
            'hypothesis': '',           # 研究假设
            'experiment_design': '',    # 实验设计
            'data_sources': [],         # 数据源
            'parameters': {},           # 参数配置
            'key_findings': [],         # 核心发现
            'learnings': [],            # 经验教训
            'next_steps': [],           # 后续步骤
            'backtest_id': '',          # 关联回测ID
            'strategy_version': '',     # 策略版本
            'git_commit': self._get_git_commit(),
            'timestamp': datetime.now().isoformat()
        }

    def _get_git_commit(self) -> str:
        """获取当前 Git Commit ID"""
        try:
            commit = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], 
                stderr=subprocess.STDOUT
            ).decode('utf-8').strip()
            return commit
        except Exception as e:
            logger.warning(f"获取 Git Commit 失败: {e}")
            return "unknown"

    def update_metadata(self, **kwargs):
        """更新元数据"""
        for key, value in kwargs.items():
            if key in self.metadata:
                self.metadata[key] = value
            else:
                logger.warning(f"未知的元数据字段: {key}")

    def save(self, filename: Optional[str] = None) -> str:
        """保存笔记为 JSON 文件"""
        if not filename:
            # 默认文件名: note_YYYYMMDD_HHMMSS.json
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"note_{timestamp}.json"
        
        file_path = self.note_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=4, ensure_ascii=False)
        
        logger.info(f"研究笔记已保存: {file_path}")
        return str(file_path)

    def to_markdown(self) -> str:
        """将笔记转换为 Markdown 格式"""
        md = f"# 研究笔记 - {self.metadata['timestamp']}\n\n"
        md += f"**Git Commit**: `{self.metadata['git_commit']}`\n"
        md += f"**Backtest ID**: `{self.metadata['backtest_id']}`\n"
        md += f"**Strategy Version**: `{self.metadata['strategy_version']}`\n\n"
        
        md += "## 1. 研究假设\n"
        md += f"{self.metadata['hypothesis'] or '未填写'}\n\n"
        
        md += "## 2. 实验设计\n"
        md += f"{self.metadata['experiment_design'] or '未填写'}\n\n"
        
        md += "## 3. 参数配置\n"
        md += "```json\n"
        md += json.dumps(self.metadata['parameters'], indent=2, ensure_ascii=False)
        md += "\n```\n\n"
        
        md += "## 4. 核心发现\n"
        for finding in self.metadata['key_findings']:
            md += f"- {finding}\n"
        if not self.metadata['key_findings']:
            md += "未记录\n"
        md += "\n"
        
        md += "## 5. 经验教训与后续步骤\n"
        md += "### 经验教训\n"
        for learning in self.metadata['learnings']:
            md += f"- {learning}\n"
        
        md += "\n### 后续步骤\n"
        for step in self.metadata['next_steps']:
            md += f"- {step}\n"
            
        return md

    def save_markdown(self, filename: Optional[str] = None) -> str:
        """保存笔记为 Markdown 文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"note_{timestamp}.md"
            
        file_path = self.note_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_markdown())
            
        logger.info(f"研究笔记已保存(Markdown): {file_path}")
        return str(file_path)

if __name__ == "__main__":
    # 示例用法
    note = ResearchNote()
    note.update_metadata(
        hypothesis="增加成交量过滤可以减少回撤",
        experiment_design="在原有策略基础上增加 vol_ma5 > vol_ma20 过滤",
        parameters={"vol_ma_short": 5, "vol_ma_long": 20},
        key_findings=["回撤从 15% 降低到 12%", "收益率略有下降"],
        learnings=["成交量过滤在震荡行情中效果显著"],
        next_steps=["测试不同周期的成交量均线组合"]
    )
    note.save()
    note.save_markdown()
