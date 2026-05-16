"""
core/portfolio/signal_engine.py 信号引擎测试

测试内容：
1. 信号数据结构
2. 信号引擎初始化
3. 信号规则管理
4. 信号生成接口
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestSignal:
    """信号数据结构测试"""
    
    def test_signal_creation(self):
        """测试信号创建"""
        from core.portfolio.signal_engine import Signal
        
        signal = Signal(
            stock_code="000001",
            stock_name="平安银行",
            signal_date="20250101",
            signal_type="buy",
            signal_name="ma20_breakout",
            signal_strength=0.8,
            price_at_signal=10.0,
            details="站上20日线"
        )
        
        assert signal.stock_code == "000001"
        assert signal.stock_name == "平安银行"
        assert signal.signal_type == "buy"
        assert signal.signal_strength == 0.8
    
    def test_signal_default_values(self):
        """测试信号默认值"""
        from core.portfolio.signal_engine import Signal
        
        signal = Signal(
            stock_code="000001",
            stock_name="平安银行",
            signal_date="20250101",
            signal_type="buy",
            signal_name="test"
        )
        
        assert signal.signal_strength == 0.0
        assert signal.price_at_signal == 0.0
        assert signal.details == ""


class TestSignalEngineInit:
    """信号引擎初始化测试"""
    
    def test_engine_creation(self):
        """测试引擎创建"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        
        assert engine is not None
        assert hasattr(engine, 'rules')
        assert hasattr(engine, 'DEFAULT_RULES')
    
    def test_engine_with_custom_rules(self, tmp_path):
        """测试自定义规则"""
        from core.portfolio.signal_engine import SignalEngine
        import json
        
        rules_path = str(tmp_path / "test_rules.json")
        custom_rules = {
            "buy_signals": {"right_side": {}},
            "sell_signals": {"right_side": {}},
            "watch_signals": {"left_side": {}}
        }
        
        with open(rules_path, 'w') as f:
            json.dump(custom_rules, f)
        
        engine = SignalEngine(rules_path=rules_path)
        
        assert engine.rules == custom_rules
    
    def test_save_rules(self, tmp_path):
        """测试保存规则"""
        from core.portfolio.signal_engine import SignalEngine
        
        rules_path = str(tmp_path / "test_rules.json")
        engine = SignalEngine(rules_path=rules_path)
        
        new_rules = {"buy_signals": {}, "sell_signals": {}, "watch_signals": {}}
        engine.save_rules(new_rules)
        
        assert engine.rules == new_rules


class TestSignalRules:
    """信号规则测试"""
    
    def test_default_rules_structure(self):
        """测试默认规则结构"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        
        assert 'buy_signals' in engine.DEFAULT_RULES
        assert 'sell_signals' in engine.DEFAULT_RULES
        assert 'watch_signals' in engine.DEFAULT_RULES
    
    def test_buy_signals_rules(self):
        """测试买入信号规则"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        buy_rules = engine.DEFAULT_RULES['buy_signals']
        
        assert 'right_side' in buy_rules
    
    def test_sell_signals_rules(self):
        """测试卖出信号规则"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        sell_rules = engine.DEFAULT_RULES['sell_signals']
        
        assert 'right_side' in sell_rules
    
    def test_watch_signals_rules(self):
        """测试观察信号规则"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        watch_rules = engine.DEFAULT_RULES['watch_signals']
        
        assert 'left_side' in watch_rules
    
    def test_ma20_breakout_rule(self):
        """测试20日突破规则"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        rule = engine.DEFAULT_RULES['buy_signals']['right_side'].get('ma20_breakout_with_bias', {})
        
        if rule:
            assert 'enabled' in rule
            assert 'bias_min' in rule
            assert 'bias_max' in rule
    
    def test_macd_golden_cross_rule(self):
        """测试MACD金叉规则"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        rule = engine.DEFAULT_RULES['buy_signals']['right_side'].get('macd_golden_cross', {})
        
        if rule:
            assert 'enabled' in rule


class TestSignalGeneration:
    """信号生成测试"""
    
    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        engine._data_adapter = Mock()
        return engine
    
    def test_generate_signals_empty(self, engine):
        """测试空股票列表"""
        signals = engine.generate_signals([])
        
        assert signals == {'buy': [], 'sell': [], 'watch': []}
    
    def test_generate_signals_structure(self, engine):
        """测试信号生成结构"""
        signals = engine.generate_signals(['000001'])
        
        assert 'buy' in signals
        assert 'sell' in signals
        assert 'watch' in signals
        assert isinstance(signals['buy'], list)
        assert isinstance(signals['sell'], list)
        assert isinstance(signals['watch'], list)


class TestSignalEngineDataAccess:
    """信号引擎数据访问测试"""
    
    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        return engine
    
    def test_get_stock_names_empty(self, engine):
        """测试空股票代码列表"""
        names = engine.get_stock_names([])
        
        assert names == {}
    
    def test_get_latest_prices_empty(self, engine):
        """测试空价格获取"""
        prices = engine.get_latest_prices([])
        
        assert prices == {}
    
    def test_get_stock_data_empty(self, engine):
        """测试空股票数据"""
        data = engine.get_stock_data("000001", days=10)
        
        assert isinstance(data, dict)


class TestSignalEngineAdapter:
    """信号引擎适配器测试"""
    
    def test_lazy_data_adapter(self):
        """测试延迟加载数据适配器"""
        from core.portfolio.signal_engine import SignalEngine
        
        engine = SignalEngine()
        
        assert engine._data_adapter is None
        
        adapter = engine._get_data_adapter()
        
        assert adapter is not None
