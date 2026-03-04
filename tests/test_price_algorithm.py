"""
价格波动算法模块单元测试
"""
import unittest
from datetime import datetime, date
from unittest.mock import patch
from src.price_algorithm import PriceAlgorithm, PriceSignal


class TestPriceAlgorithm(unittest.TestCase):
    """测试 PriceAlgorithm"""

    def setUp(self):
        self.algo = PriceAlgorithm({'threshold': 5})

    def test_init_default_threshold(self):
        algo = PriceAlgorithm({})
        self.assertEqual(algo.threshold, 5)

    def test_init_custom_threshold(self):
        algo = PriceAlgorithm({'threshold': 10})
        self.assertEqual(algo.threshold, 10)

    def test_first_update_no_signal(self):
        """第一次更新不应产生信号"""
        result = self.algo.update(680.0)
        self.assertIsNone(result)

    def test_small_change_no_signal(self):
        """小幅波动不应产生信号"""
        self.algo.update(680.0)
        result = self.algo.update(682.0)
        self.assertIsNone(result)
        result = self.algo.update(678.0)  # 跌4，未超过阈值5
        self.assertIsNone(result)

    def test_drop_signal(self):
        """跌超过阈值应触发跌幅信号"""
        self.algo.update(680.0)
        self.algo.update(688.0)  # 新高
        result = self.algo.update(682.0)  # 跌6，超过阈值5
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, 'DROP')
        self.assertAlmostEqual(result.change, 6.0)
        self.assertAlmostEqual(result.price, 682.0)

    def test_rise_signal(self):
        """涨超过阈值应触发涨幅信号"""
        self.algo.update(688.0)
        self.algo.update(680.0)  # 新低
        result = self.algo.update(686.0)  # 涨6，超过阈值5
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, 'RISE')
        self.assertAlmostEqual(result.change, 6.0)
        self.assertAlmostEqual(result.price, 686.0)

    def test_continuous_drop_multiple_signals(self):
        """持续下跌应触发多次信号"""
        self.algo.update(700.0)
        
        # 第一次跌
        sig1 = self.algo.update(694.0)  # 跌6
        self.assertIsNotNone(sig1)
        self.assertEqual(sig1.signal_type, 'DROP')
        
        # 继续跌，基准已更新为694
        sig2 = self.algo.update(688.0)  # 从694跌6
        self.assertIsNotNone(sig2)
        self.assertEqual(sig2.signal_type, 'DROP')

    def test_continuous_rise_multiple_signals(self):
        """持续上涨应触发多次信号"""
        self.algo.update(680.0)
        
        sig1 = self.algo.update(686.0)  # 涨6
        self.assertIsNotNone(sig1)
        self.assertEqual(sig1.signal_type, 'RISE')
        
        # 继续涨，基准已更新为686
        sig2 = self.algo.update(692.0)  # 从686涨6
        self.assertIsNotNone(sig2)
        self.assertEqual(sig2.signal_type, 'RISE')

    def test_cross_day_reset(self):
        """跨天应重置状态"""
        self.algo.update(680.0)
        self.algo.update(690.0)
        
        # 模拟跨天
        self.algo._current_date = date(2025, 1, 1)
        result = self.algo.update(685.0)
        
        # 跨天后第一次更新，不应有信号
        self.assertIsNone(result)
        # high 和 low 应该被重置为当前价格
        self.assertEqual(self.algo._today_high, 685.0)
        self.assertEqual(self.algo._today_low, 685.0)

    def test_exact_threshold_triggers(self):
        """恰好等于阈值应触发信号"""
        self.algo.update(680.0)
        self.algo.update(690.0)  # 高点690
        result = self.algo.update(685.0)  # 跌5，恰好等于阈值
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, 'DROP')

    def test_get_status(self):
        """测试状态获取"""
        self.algo.update(680.0)
        status = self.algo.get_status()
        self.assertEqual(status['today_high'], 680.0)
        self.assertEqual(status['today_low'], 680.0)
        self.assertEqual(status['threshold'], 5)
        self.assertEqual(status['update_count'], 1)

    def test_signal_data_structure(self):
        """测试信号数据结构完整性"""
        self.algo.update(690.0)
        self.algo.update(680.0)
        signal = self.algo.update(686.0)
        
        self.assertIsInstance(signal, PriceSignal)
        self.assertIsInstance(signal.timestamp, datetime)
        self.assertIn(signal.signal_type, ['RISE', 'DROP'])
        self.assertIsInstance(signal.price, float)
        self.assertIsInstance(signal.today_high, float)
        self.assertIsInstance(signal.today_low, float)
        self.assertIsInstance(signal.change, float)
        self.assertIsInstance(signal.reference_price, float)
        self.assertIsInstance(signal.reasons, list)
        self.assertTrue(len(signal.reasons) > 0)


if __name__ == '__main__':
    unittest.main()
