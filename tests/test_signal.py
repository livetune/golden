"""
单元测试 - 信号生成模块测试
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signal_generator import SignalGenerator, Signal


class TestSignalGenerator(unittest.TestCase):
    """信号生成器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = {
            'ma_period': 20,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'min_conditions': 2
        }
        self.generator = SignalGenerator(self.config)
    
    def _create_test_data(self, n: int = 50, trend: str = 'up') -> pd.DataFrame:
        """创建测试数据"""
        dates = pd.date_range(start='2024-01-01', periods=n, freq='1min')
        np.random.seed(42)
        
        if trend == 'up':
            prices = 2000 + np.cumsum(np.abs(np.random.randn(n)) * 0.5)
        elif trend == 'down':
            prices = 2000 - np.cumsum(np.abs(np.random.randn(n)) * 0.5)
        else:
            prices = 2000 + np.cumsum(np.random.randn(n) * 0.5)
        
        return pd.DataFrame({
            'close': prices,
            'open': prices - 1,
            'high': prices + 2,
            'low': prices - 2
        }, index=dates)
    
    def test_calculate_ma(self):
        """测试MA计算"""
        df = self._create_test_data(30)
        ma = self.generator.calculate_ma(df)
        
        self.assertFalse(ma.empty)
        self.assertEqual(len(ma), len(df))
        # 前19个值应该是NaN
        self.assertTrue(pd.isna(ma.iloc[0]))
        # 第20个值应该有值
        self.assertFalse(pd.isna(ma.iloc[19]))
    
    def test_calculate_rsi(self):
        """测试RSI计算"""
        df = self._create_test_data(30)
        rsi = self.generator.calculate_rsi(df)
        
        self.assertFalse(rsi.empty)
        # RSI值应该在0-100之间
        valid_rsi = rsi.dropna()
        self.assertTrue(all(0 <= v <= 100 for v in valid_rsi))
    
    def test_calculate_macd(self):
        """测试MACD计算"""
        df = self._create_test_data(50)
        dif, dea, macd_hist = self.generator.calculate_macd(df)
        
        self.assertFalse(dif.empty)
        self.assertFalse(dea.empty)
        self.assertFalse(macd_hist.empty)
    
    def test_check_ma_signal(self):
        """测试MA信号检测"""
        df = self._create_test_data(30, trend='up')
        triggered, reason = self.generator.check_ma_signal(df)
        
        self.assertIsInstance(triggered, bool)
        self.assertIsInstance(reason, str)
    
    def test_check_rsi_signal(self):
        """测试RSI信号检测"""
        df = self._create_test_data(30)
        triggered, reason = self.generator.check_rsi_signal(df)
        
        self.assertIsInstance(triggered, bool)
        self.assertIsInstance(reason, str)
    
    def test_check_macd_signal(self):
        """测试MACD信号检测"""
        df = self._create_test_data(50)
        triggered, reason = self.generator.check_macd_signal(df)
        
        self.assertIsInstance(triggered, bool)
        self.assertIsInstance(reason, str)
    
    def test_generate_signal_insufficient_data(self):
        """测试数据不足时的信号生成"""
        df = self._create_test_data(10)  # 数据不足
        signal = self.generator.generate_signal(df)
        
        self.assertIsNone(signal)
    
    def test_generate_signal_with_data(self):
        """测试正常数据的信号生成"""
        df = self._create_test_data(50)
        signal = self.generator.generate_signal(df)
        
        # 信号可能为None或Signal对象
        if signal:
            self.assertIsInstance(signal, Signal)
            self.assertIn(signal.signal_type, ['BUY', 'SELL', 'HOLD'])
            self.assertGreaterEqual(signal.strength, 1)
            self.assertLessEqual(signal.strength, 3)
    
    def test_get_analysis_summary(self):
        """测试分析摘要"""
        df = self._create_test_data(50)
        summary = self.generator.get_analysis_summary(df)
        
        self.assertIn('current_price', summary)
        self.assertIn('ma', summary)
        self.assertIn('rsi', summary)
        self.assertIn('macd', summary)


class TestDataStructures(unittest.TestCase):
    """数据结构测试"""
    
    def test_signal_dataclass(self):
        """测试Signal数据类"""
        signal = Signal(
            timestamp=datetime.now(),
            signal_type='BUY',
            strength=2,
            price=2045.50,
            reasons=['test reason'],
            indicators={'ma': 2040.0}
        )
        
        self.assertEqual(signal.signal_type, 'BUY')
        self.assertEqual(signal.strength, 2)
        self.assertEqual(signal.price, 2045.50)


if __name__ == '__main__':
    unittest.main(verbosity=2)
