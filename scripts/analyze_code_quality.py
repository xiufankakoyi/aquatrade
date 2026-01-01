#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代码质量分析工具
分析各模块的代码复杂度、冗余度、可读性
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

class CodeAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = defaultdict(dict)
    
    def analyze_file(self, file_path: Path) -> Dict:
        """分析单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except Exception as e:
            return {'error': str(e)}
        
        lines = content.split('\n')
        total_lines = len(lines)
        code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
        blank_lines = len([l for l in lines if not l.strip()])
        comment_lines = len([l for l in lines if l.strip().startswith('#')])
        
        # 统计函数和类
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        
        # 统计导入
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        
        # 计算复杂度（简单指标：嵌套深度）
        max_depth = self._calculate_max_depth(tree)
        
        # 查找重复代码模式
        duplicate_patterns = self._find_duplicate_patterns(functions)
        
        return {
            'total_lines': total_lines,
            'code_lines': code_lines,
            'blank_lines': blank_lines,
            'comment_lines': comment_lines,
            'functions': len(functions),
            'classes': len(classes),
            'imports': len(imports),
            'max_depth': max_depth,
            'duplicate_patterns': len(duplicate_patterns),
            'function_names': [f.name for f in functions],
            'class_names': [c.name for c in classes],
        }
    
    def _calculate_max_depth(self, node, depth=0):
        """计算最大嵌套深度"""
        max_d = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                max_d = max(max_d, self._calculate_max_depth(child, depth + 1))
            else:
                max_d = max(max_d, self._calculate_max_depth(child, depth))
        return max_d
    
    def _find_duplicate_patterns(self, functions: List[ast.FunctionDef]) -> List[Tuple]:
        """查找重复的代码模式"""
        patterns = []
        for i, f1 in enumerate(functions):
            for j, f2 in enumerate(functions[i+1:], i+1):
                # 简单比较：函数体行数相似且名称相似
                if abs(len(f1.body) - len(f2.body)) < 3:
                    if f1.name != f2.name and (
                        f1.name.replace('_', '') == f2.name.replace('_', '') or
                        f1.name in f2.name or f2.name in f1.name
                    ):
                        patterns.append((f1.name, f2.name))
        return patterns
    
    def analyze_module(self, module_path: Path) -> Dict:
        """分析整个模块"""
        module_results = {
            'files': {},
            'total_files': 0,
            'total_lines': 0,
            'total_functions': 0,
            'total_classes': 0,
            'issues': []
        }
        
        if not module_path.exists():
            return module_results
        
        # 分析所有 Python 文件
        for py_file in module_path.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            
            rel_path = py_file.relative_to(self.project_root)
            file_result = self.analyze_file(py_file)
            
            if 'error' not in file_result:
                module_results['files'][str(rel_path)] = file_result
                module_results['total_files'] += 1
                module_results['total_lines'] += file_result['total_lines']
                module_results['total_functions'] += file_result['functions']
                module_results['total_classes'] += file_result['classes']
                
                # 检查问题
                if file_result['total_lines'] > 1000:
                    module_results['issues'].append(f"{rel_path}: 文件过大 ({file_result['total_lines']} 行)")
                if file_result['functions'] > 30:
                    module_results['issues'].append(f"{rel_path}: 函数过多 ({file_result['functions']} 个)")
                if file_result['max_depth'] > 5:
                    module_results['issues'].append(f"{rel_path}: 嵌套过深 (深度 {file_result['max_depth']})")
                if file_result['duplicate_patterns'] > 0:
                    module_results['issues'].append(f"{rel_path}: 发现 {file_result['duplicate_patterns']} 个重复模式")
        
        return module_results
    
    def generate_report(self) -> str:
        """生成分析报告"""
        report = []
        report.append("=" * 80)
        report.append("代码质量分析报告")
        report.append("=" * 80)
        report.append("")
        
        # 分析主要模块
        modules = {
            'server': self.project_root / 'server',
            'core': self.project_root / 'core',
            'data_svc': self.project_root / 'data_svc',
        }
        
        for module_name, module_path in modules.items():
            report.append(f"\n## {module_name.upper()} 模块")
            report.append("-" * 80)
            
            result = self.analyze_module(module_path)
            
            report.append(f"总文件数: {result['total_files']}")
            report.append(f"总代码行数: {result['total_lines']:,}")
            report.append(f"总函数数: {result['total_functions']}")
            report.append(f"总类数: {result['total_classes']}")
            report.append("")
            
            if result['issues']:
                report.append("[WARN] 发现的问题:")
                for issue in result['issues']:
                    report.append(f"  - {issue}")
                report.append("")
            
            # 列出大文件
            large_files = sorted(
                [(path, data['total_lines']) for path, data in result['files'].items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            if large_files:
                report.append("[INFO] 最大的文件:")
                for path, lines in large_files:
                    report.append(f"  - {path}: {lines:,} 行")
                report.append("")
        
        return "\n".join(report)

def main():
    project_root = Path(__file__).parent.parent
    analyzer = CodeAnalyzer(project_root)
    report = analyzer.generate_report()
    print(report)
    
    # 保存报告
    report_file = project_root / 'docs' / 'CODE_QUALITY_ANALYSIS.md'
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报告已保存到: {report_file}")

if __name__ == "__main__":
    main()

