"""
导出相关路由
============

提供 Excel 和 PDF 导出功能
"""
from flask import Blueprint, request, send_file
from server.performance_utils import json_response
import pandas as pd
import io
from datetime import datetime
from config.logger import get_logger

logger = get_logger(__name__)
export_bp = Blueprint('export', __name__, url_prefix='/api/export')


@export_bp.route('/excel', methods=['POST', 'OPTIONS'])
def export_excel():
    """
    导出回测数据到 Excel
    
    请求体:
        {
            "strategy_id": "策略ID",
            "backtest_result": {
                "metrics": {...},
                "equityCurve": [...],
                "monthlyReturns": [...],
                "trades": [...],
                "strategyInfo": {"name": "策略名称"}
            }
        }
    
    返回:
        Excel 文件下载
    """
    if request.method == 'OPTIONS':
        return json_response({'success': True})
    
    try:
        data = request.get_json() or {}
        backtest_result = data.get('backtest_result', {})
        
        strategy_name = backtest_result.get('strategyInfo', {}).get('name', '未知策略')
        metrics = backtest_result.get('metrics', {})
        equity_curve = backtest_result.get('equityCurve', [])
        monthly_returns = backtest_result.get('monthlyReturns', [])
        trades = backtest_result.get('trades', [])
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if metrics:
                metrics_df = pd.DataFrame([{
                    '策略名称': strategy_name,
                    '年化收益率 (%)': metrics.get('annualizedReturn'),
                    '夏普比率': metrics.get('sharpeRatio'),
                    '最大回撤 (%)': metrics.get('maxDrawdown'),
                    '胜率 (%)': metrics.get('winRate'),
                    '盈亏比': metrics.get('profitFactor'),
                    '交易次数': metrics.get('tradesCount'),
                    '总收益 (%)': metrics.get('totalReturn'),
                }])
                metrics_df.to_excel(writer, sheet_name='策略指标', index=False)
            
            if equity_curve:
                equity_df = pd.DataFrame(equity_curve)
                if 'date' in equity_df.columns and 'equity' in equity_df.columns:
                    equity_df = equity_df[['date', 'equity']]
                    equity_df.columns = ['日期', '净值']
                equity_df.to_excel(writer, sheet_name='净值曲线', index=False)
            
            if monthly_returns:
                monthly_df = pd.DataFrame(monthly_returns)
                monthly_df.to_excel(writer, sheet_name='月度收益', index=False)
            
            if trades:
                trades_df = pd.DataFrame(trades)
                trades_df.to_excel(writer, sheet_name='交易记录', index=False)
        
        output.seek(0)
        
        filename = f"回测数据_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            attachment_filename=filename
        )
        
    except Exception as e:
        logger.error(f"导出 Excel 失败: {e}", exc_info=True)
        return json_response({'success': False, 'error': str(e)}, status_code=500)


@export_bp.route('/pdf', methods=['POST', 'OPTIONS'])
def export_pdf():
    """
    导出分析报告到 PDF
    
    请求体:
        {
            "strategy_id": "策略ID",
            "backtest_result": {...},
            "analysis_report": "分析报告文本"
        }
    
    返回:
        PDF 文件下载
    """
    if request.method == 'OPTIONS':
        return json_response({'success': True})
    
    try:
        data = request.get_json() or {}
        backtest_result = data.get('backtest_result', {})
        analysis_report = data.get('analysis_report', '')
        
        strategy_name = backtest_result.get('strategyInfo', {}).get('name', '未知策略')
        metrics = backtest_result.get('metrics', {})
        
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)
            styles = getSampleStyleSheet()
            
            elements = []
            
            elements.append(Paragraph(f"策略分析报告: {strategy_name}", styles['Title']))
            elements.append(Spacer(1, 20))
            
            if metrics:
                elements.append(Paragraph("策略指标", styles['Heading2']))
                table_data = [
                    ['指标', '数值'],
                    ['年化收益率', f"{metrics.get('annualizedReturn', 'N/A')}%"],
                    ['夏普比率', f"{metrics.get('sharpeRatio', 'N/A')}"],
                    ['最大回撤', f"{metrics.get('maxDrawdown', 'N/A')}%"],
                    ['胜率', f"{metrics.get('winRate', 'N/A')}%"],
                ]
                table = Table(table_data, colWidths=[200, 200])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 20))
            
            if analysis_report:
                elements.append(Paragraph("分析报告", styles['Heading2']))
                for line in analysis_report.split('\n'):
                    if line.strip():
                        elements.append(Paragraph(line, styles['Normal']))
            
            doc.build(elements)
            output.seek(0)
            
            filename = f"分析报告_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
            
        except ImportError:
            logger.warning("reportlab 未安装，返回简化版 PDF")
            output = io.BytesIO()
            content = f"""策略分析报告
            
策略名称: {strategy_name}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

策略指标:
- 年化收益率: {metrics.get('annualizedReturn', 'N/A')}%
- 夏普比率: {metrics.get('sharpeRatio', 'N/A')}
- 最大回撤: {metrics.get('maxDrawdown', 'N/A')}%
- 胜率: {metrics.get('winRate', 'N/A')}%

分析报告:
{analysis_report}
"""
            output.write(content.encode('utf-8'))
            output.seek(0)
            
            filename = f"分析报告_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            return send_file(
                output,
                mimetype='text/plain',
                as_attachment=True,
                download_name=filename
            )
        
    except Exception as e:
        logger.error(f"导出 PDF 失败: {e}", exc_info=True)
        return json_response({'success': False, 'error': str(e)}, status_code=500)
