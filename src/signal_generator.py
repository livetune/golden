"""
信号生成模块 - MA均线、RSI、MACD技术指标计算与买入信号判断
"""
import pandas as pd
import numpy as np
import logging
import gc
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SignalStrength:
    """信号强度详细评分"""
    total_score: float        # 综合评分 0-100
    level: str                # 强度等级: 极弱/弱/中等/强/极强
    ma_score: float           # MA指标得分 0-100
    rsi_score: float          # RSI指标得分 0-100
    macd_score: float         # MACD指标得分 0-100
    trend_score: float        # 趋势确认得分 0-100
    position_score: float     # 价格位置得分 0-100
    details: dict             # 评分细节


@dataclass
class Signal:
    """交易信号数据结构"""
    timestamp: datetime
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    strength: int     # 信号强度 1-5 (向后兼容)
    strength_detail: SignalStrength  # 详细强度评分
    price: float
    reasons: list     # 触发原因列表
    indicators: dict  # 指标详情


class SignalGenerator:
    """信号生成器 - 基于MA、RSI、MACD技术指标"""
    
    def __init__(self, config: dict):
        """
        初始化信号生成器
        
        Args:
            config: 指标配置参数
        """
        # MA参数
        self.ma_period = config.get('ma_period', 20)
        self.ma_short_period = config.get('ma_short_period', 5)   # 短期MA
        self.ma_long_period = config.get('ma_long_period', 60)    # 长期MA
        
        # RSI参数
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.rsi_extreme_oversold = config.get('rsi_extreme_oversold', 20)  # 极度超卖
        
        # MACD参数
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        
        # 信号配置
        self.min_conditions = config.get('min_conditions', 2)
        self.min_strength_score = config.get('min_strength_score', 40)  # 最低强度评分
        
        self._last_signal_time: Optional[datetime] = None
        
        # 计算计数器，用于定期垃圾回收
        self._calc_count = 0
        self._gc_interval = 50
    
    # ==================== 强度评分方法 ====================
    
    def _calculate_ma_score(self, data: pd.DataFrame) -> Tuple[float, dict]:
        """
        计算MA指标强度得分 (0-100) - 偏向低吸策略
        
        评分维度:
        - 价格相对MA位置: 35分 (接近或低于MA更好)
        - 价格开始企稳/反弹: 35分
        - 均线趋势: 30分
        """
        score = 0.0
        details = {}
        
        if len(data) < self.ma_long_period:
            return 0.0, {'error': '数据不足'}
        
        current_price = data['close'].iloc[-1]
        prev_price = data['close'].iloc[-2]
        
        # 计算多周期MA
        ma_short = self.calculate_ma(data, self.ma_short_period)
        ma_mid = self.calculate_ma(data, self.ma_period)
        ma_long = self.calculate_ma(data, self.ma_long_period)
        
        if ma_short.empty or ma_mid.empty or ma_long.empty:
            return 0.0, {'error': 'MA计算失败'}
        
        current_ma_short = ma_short.iloc[-1]
        current_ma_mid = ma_mid.iloc[-1]
        current_ma_long = ma_long.iloc[-1]
        prev_ma_mid = ma_mid.iloc[-2]
        
        # 1. 价格相对MA位置得分 (35分) - 低吸策略：接近或低于MA得分更高
        position_score = 0
        price_distance_pct = (current_price - current_ma_mid) / current_ma_mid * 100
        
        if -2 <= price_distance_pct <= 0:
            position_score = 35  # 略低于MA，最佳买入点
            details['ma_position'] = f'略低于MA({price_distance_pct:.2f}%)最佳'
        elif -4 <= price_distance_pct < -2:
            position_score = 30  # 低于MA
            details['ma_position'] = f'低于MA({price_distance_pct:.2f}%)'
        elif 0 < price_distance_pct <= 1:
            position_score = 30  # 刚突破MA
            details['ma_position'] = f'刚突破MA({price_distance_pct:.2f}%)'
        elif -6 <= price_distance_pct < -4:
            position_score = 25  # 明显低于MA
            details['ma_position'] = f'明显低于MA({price_distance_pct:.2f}%)'
        elif 1 < price_distance_pct <= 2:
            position_score = 20
            details['ma_position'] = f'高于MA({price_distance_pct:.2f}%)'
        elif price_distance_pct < -6:
            position_score = 15  # 远低于MA，可能还在下跌
            details['ma_position'] = f'远低于MA({price_distance_pct:.2f}%)可能继续下跌'
        else:
            position_score = 10  # 远高于MA
            details['ma_position'] = f'远高于MA({price_distance_pct:.2f}%)不建议追高'
        score += position_score
        details['position_score'] = position_score
        details['price_distance_pct'] = round(price_distance_pct, 2)
        
        # 2. 价格企稳/反弹信号 (35分)
        stabilize_score = 0
        
        # 检测价格是否开始从MA下方反弹
        if price_distance_pct < 0:  # 价格在MA下方
            if current_price > prev_price:  # 价格上涨
                stabilize_score = 35  # MA下方反弹，最佳信号
                details['stabilize'] = 'MA下方开始反弹(最佳)'
            elif current_price >= prev_price * 0.999:  # 价格企稳
                stabilize_score = 25
                details['stabilize'] = 'MA下方企稳'
            else:
                stabilize_score = 10
                details['stabilize'] = 'MA下方继续下跌'
        elif prev_price < prev_ma_mid and current_price >= current_ma_mid:
            # 价格从MA下方穿越到上方
            stabilize_score = 30
            details['stabilize'] = '突破MA均线'
        elif current_price > prev_price:
            stabilize_score = 20
            details['stabilize'] = 'MA上方上涨'
        else:
            stabilize_score = 10
            details['stabilize'] = 'MA上方'
        score += stabilize_score
        details['stabilize_score'] = stabilize_score
        
        # 3. 均线趋势得分 (30分) - 检测均线是否开始走平或上翘
        trend_score = 0
        if len(ma_mid) >= 5:
            ma_slope = (ma_mid.iloc[-1] - ma_mid.iloc[-5]) / ma_mid.iloc[-5] * 100
            ma_slope_recent = (ma_mid.iloc[-1] - ma_mid.iloc[-2]) / ma_mid.iloc[-2] * 100
            
            # 均线开始上翘
            if ma_slope_recent > 0 and ma_slope > -0.2:
                trend_score = 30
                details['ma_trend'] = '均线上翘'
            elif ma_slope_recent > 0:
                trend_score = 25
                details['ma_trend'] = '均线开始走平'
            elif ma_slope > -0.3:
                trend_score = 20
                details['ma_trend'] = '均线走平'
            elif ma_slope > -0.5:
                trend_score = 15
                details['ma_trend'] = '均线小幅下降'
            else:
                trend_score = 5
                details['ma_trend'] = '均线下降'
            details['ma_slope_pct'] = round(ma_slope, 3)
        score += trend_score
        details['trend_score'] = trend_score
        
        return min(100, score), details
    
    def _calculate_rsi_score(self, data: pd.DataFrame) -> Tuple[float, dict]:
        """
        计算RSI指标强度得分 (0-100)
        
        评分维度:
        - 超卖程度: 40分
        - 回升动能: 30分
        - RSI底背离: 30分
        """
        score = 0.0
        details = {}
        
        rsi = self.calculate_rsi(data)
        if rsi.empty or len(rsi) < 5:
            return 0.0, {'error': 'RSI计算失败'}
        
        current_rsi = rsi.iloc[-1]
        if pd.isna(current_rsi):
            return 0.0, {'error': 'RSI数据无效'}
        
        details['current_rsi'] = round(current_rsi, 2)
        
        # 1. 超卖程度得分 (40分)
        oversold_score = 0
        if current_rsi <= self.rsi_extreme_oversold:
            oversold_score = 40  # 极度超卖
            details['oversold_level'] = '极度超卖'
        elif current_rsi <= self.rsi_oversold:
            # 20-30之间，越低分越高
            oversold_score = 25 + (self.rsi_oversold - current_rsi) * 1.5
            details['oversold_level'] = '超卖'
        elif current_rsi <= 40:
            oversold_score = 15  # 偏弱
            details['oversold_level'] = '偏弱'
        elif current_rsi <= 50:
            oversold_score = 10  # 中性偏弱
            details['oversold_level'] = '中性'
        else:
            oversold_score = 0
            details['oversold_level'] = '正常或偏强'
        score += oversold_score
        details['oversold_score'] = round(oversold_score, 1)
        
        # 2. 回升动能得分 (30分)
        momentum_score = 0
        rsi_change = current_rsi - rsi.iloc[-2]
        rsi_change_3 = current_rsi - rsi.iloc[-3] if len(rsi) >= 3 else 0
        
        if rsi.iloc[-2] < self.rsi_oversold <= current_rsi:
            momentum_score = 30  # 从超卖区突破
            details['momentum'] = '从超卖区突破'
        elif rsi_change > 5:
            momentum_score = 25  # 强劲回升
            details['momentum'] = '强劲回升'
        elif rsi_change > 2:
            momentum_score = 20
            details['momentum'] = '明显回升'
        elif rsi_change > 0:
            momentum_score = 10
            details['momentum'] = '小幅回升'
        elif rsi_change > -2:
            momentum_score = 5
            details['momentum'] = '横盘整理'
        else:
            details['momentum'] = '继续下跌'
        score += momentum_score
        details['momentum_score'] = momentum_score
        details['rsi_change'] = round(rsi_change, 2)
        
        # 3. RSI底背离检测 (30分)
        divergence_score = 0
        if len(data) >= 20 and len(rsi) >= 20:
            # 检测最近20根K线是否有底背离
            prices = data['close'].iloc[-20:]
            rsi_values = rsi.iloc[-20:]
            
            # 简化的底背离检测：价格创新低但RSI不创新低
            price_min_idx = prices.idxmin()
            price_min = prices.min()
            rsi_at_price_min = rsi_values.loc[price_min_idx] if price_min_idx in rsi_values.index else None
            
            current_price = data['close'].iloc[-1]
            # 如果当前价格接近最低点但RSI高于最低点时的RSI
            if rsi_at_price_min is not None:
                if current_price <= price_min * 1.02 and current_rsi > rsi_at_price_min + 3:
                    divergence_score = 30
                    details['divergence'] = '检测到底背离'
                elif current_price <= price_min * 1.05 and current_rsi > rsi_at_price_min:
                    divergence_score = 15
                    details['divergence'] = '可能存在底背离'
        score += divergence_score
        details['divergence_score'] = divergence_score
        
        return min(100, score), details
    
    def _calculate_macd_score(self, data: pd.DataFrame) -> Tuple[float, dict]:
        """
        计算MACD指标强度得分 (0-100)
        
        评分维度:
        - 金叉质量: 35分
        - 柱状图动能: 25分
        - 零轴位置: 20分
        - 背离检测: 20分
        """
        score = 0.0
        details = {}
        
        dif, dea, macd_hist = self.calculate_macd(data)
        if dif.empty or len(dif) < 5:
            return 0.0, {'error': 'MACD计算失败'}
        
        current_dif = dif.iloc[-1]
        prev_dif = dif.iloc[-2]
        current_dea = dea.iloc[-1]
        prev_dea = dea.iloc[-2]
        current_hist = macd_hist.iloc[-1]
        prev_hist = macd_hist.iloc[-2]
        
        if pd.isna(current_dif) or pd.isna(current_dea):
            return 0.0, {'error': 'MACD数据无效'}
        
        details['dif'] = round(current_dif, 4)
        details['dea'] = round(current_dea, 4)
        details['hist'] = round(current_hist, 4)
        
        # 1. 金叉质量得分 (35分)
        golden_cross_score = 0
        if prev_dif < prev_dea and current_dif > current_dea:
            # 金叉发生
            cross_strength = current_dif - current_dea
            if current_dif > 0:
                golden_cross_score = 35  # 零轴上方金叉，最强
                details['cross_type'] = '零轴上方金叉(最强)'
            elif current_dif > -abs(current_dea) * 0.5:
                golden_cross_score = 30  # 接近零轴金叉
                details['cross_type'] = '接近零轴金叉'
            else:
                golden_cross_score = 25  # 低位金叉
                details['cross_type'] = '低位金叉'
        elif current_dif > current_dea:
            # 已经在金叉状态
            if current_dif > prev_dif:
                golden_cross_score = 20  # 金叉后继续扩大
                details['cross_type'] = '金叉后扩张'
            else:
                golden_cross_score = 10
                details['cross_type'] = '金叉后收敛'
        else:
            details['cross_type'] = '未形成金叉'
        score += golden_cross_score
        details['cross_score'] = golden_cross_score
        
        # 2. 柱状图动能得分 (25分)
        histogram_score = 0
        hist_change = current_hist - prev_hist
        
        if current_hist > 0 and hist_change > 0:
            histogram_score = 25  # 红柱且放大
            details['histogram_trend'] = '红柱放大'
        elif current_hist > 0:
            histogram_score = 20  # 红柱
            details['histogram_trend'] = '红柱'
        elif current_hist < 0 and hist_change > 0:
            histogram_score = 15  # 绿柱缩小
            details['histogram_trend'] = '绿柱缩小'
        elif prev_hist < current_hist < 0:
            histogram_score = 10
            details['histogram_trend'] = '绿柱收窄'
        else:
            details['histogram_trend'] = '绿柱扩大'
        score += histogram_score
        details['histogram_score'] = histogram_score
        
        # 3. 零轴位置得分 (20分)
        zero_axis_score = 0
        if current_dif > 0 and current_dea > 0:
            zero_axis_score = 20  # 双线在零轴上方
            details['zero_position'] = '双线零轴上方'
        elif current_dif > 0:
            zero_axis_score = 15
            details['zero_position'] = 'DIF在零轴上方'
        elif current_dif > prev_dif:
            zero_axis_score = 10  # DIF向上
            details['zero_position'] = 'DIF向上靠近零轴'
        else:
            zero_axis_score = 5
            details['zero_position'] = '双线零轴下方'
        score += zero_axis_score
        details['zero_axis_score'] = zero_axis_score
        
        # 4. 背离检测得分 (20分)
        divergence_score = 0
        if len(data) >= 20:
            prices = data['close'].iloc[-20:]
            dif_values = dif.iloc[-20:]
            
            price_min = prices.min()
            current_price = data['close'].iloc[-1]
            
            # 简化背离检测
            if current_price <= price_min * 1.02 and current_dif > dif_values.min() * 0.8:
                divergence_score = 20
                details['macd_divergence'] = '检测到底背离'
            elif current_price <= price_min * 1.05:
                divergence_score = 10
                details['macd_divergence'] = '可能存在底背离'
        score += divergence_score
        details['divergence_score'] = divergence_score
        
        return min(100, score), details
    
    def _calculate_trend_score(self, data: pd.DataFrame) -> Tuple[float, dict]:
        """
        计算趋势确认得分 (0-100) - 偏向低吸策略
        
        评分维度:
        - 价格位置(相对近期区间): 40分
        - 企稳/反弹信号: 35分
        - 波动率: 25分
        """
        score = 0.0
        details = {}
        
        if len(data) < 20:
            return 0.0, {'error': '数据不足'}
        
        closes = data['close']
        current_price = closes.iloc[-1]
        prev_price = closes.iloc[-2]
        
        # 1. 价格位置得分 (40分) - 越低越好
        position_score = 0
        low_20d = data['low'].iloc[-20:].min() if 'low' in data.columns else closes.iloc[-20:].min()
        high_20d = data['high'].iloc[-20:].max() if 'high' in data.columns else closes.iloc[-20:].max()
        
        price_range = high_20d - low_20d
        if price_range > 0:
            position_pct = (current_price - low_20d) / price_range * 100
            
            # 低吸策略：接近低点得分更高
            if position_pct <= 15:
                position_score = 40  # 极低位
                details['range_position'] = f'极低位({position_pct:.1f}%)'
            elif position_pct <= 25:
                position_score = 35
                details['range_position'] = f'低位({position_pct:.1f}%)'
            elif position_pct <= 40:
                position_score = 30
                details['range_position'] = f'偏低位({position_pct:.1f}%)'
            elif position_pct <= 55:
                position_score = 20
                details['range_position'] = f'中间位({position_pct:.1f}%)'
            elif position_pct <= 70:
                position_score = 10
                details['range_position'] = f'偏高位({position_pct:.1f}%)'
            else:
                position_score = 0
                details['range_position'] = f'高位({position_pct:.1f}%)不建议买入'
            
            details['position_in_range'] = round(position_pct, 1)
        score += position_score
        details['position_score'] = position_score
        
        # 2. 企稳/反弹信号得分 (35分)
        stabilize_score = 0
        
        # 计算近期走势
        price_change_1 = (current_price - prev_price) / prev_price * 100
        price_change_3 = (current_price - closes.iloc[-3]) / closes.iloc[-3] * 100 if len(closes) >= 3 else 0
        
        # 检测反弹/企稳信号
        if price_change_1 > 0 and price_change_3 > 0:
            stabilize_score = 35  # 连续反弹
            details['trend_signal'] = '连续反弹中'
        elif price_change_1 > 0:
            stabilize_score = 30  # 开始反弹
            details['trend_signal'] = '开始反弹'
        elif abs(price_change_1) < 0.1:
            stabilize_score = 25  # 企稳
            details['trend_signal'] = '企稳整理'
        elif price_change_1 > -0.2:
            stabilize_score = 20
            details['trend_signal'] = '小幅回调'
        elif price_change_1 > -0.5:
            stabilize_score = 15
            details['trend_signal'] = '下跌放缓'
        else:
            stabilize_score = 5
            details['trend_signal'] = '持续下跌'
        
        score += stabilize_score
        details['stabilize_score'] = stabilize_score
        details['price_change_1'] = round(price_change_1, 2)
        
        # 3. 波动率得分 (25分) - 适度波动
        volatility_score = 0
        returns = closes.pct_change().dropna()
        if len(returns) >= 10:
            volatility = returns.iloc[-10:].std() * 100
            
            if 0.3 <= volatility <= 1.0:
                volatility_score = 25  # 适度波动
                details['volatility_level'] = '适度波动(适合买入)'
            elif 0.1 <= volatility < 0.3:
                volatility_score = 20  # 低波动
                details['volatility_level'] = '低波动'
            elif 1.0 < volatility <= 1.5:
                volatility_score = 20
                details['volatility_level'] = '较高波动'
            elif 1.5 < volatility <= 2.5:
                volatility_score = 15
                details['volatility_level'] = '高波动'
            else:
                volatility_score = 10
                details['volatility_level'] = '极端波动(风险高)'
            
            details['volatility_pct'] = round(volatility, 3)
        score += volatility_score
        details['volatility_score'] = volatility_score
        
        return min(100, score), details
    
    def _calculate_position_score(self, data: pd.DataFrame) -> Tuple[float, dict]:
        """
        计算价格位置得分 (0-100) - 偏向低吸策略
        
        评分维度:
        - 相对历史位置: 60分 (越低越好)
        - 反弹信号: 40分
        """
        score = 0.0
        details = {}
        
        if len(data) < 20:
            return 0.0, {'error': '数据不足'}
        
        current_price = data['close'].iloc[-1]
        prev_price = data['close'].iloc[-2]
        
        # 1. 相对历史位置 (60分) - 价格越低分数越高
        position_score = 0
        high_20d = data['high'].iloc[-20:].max() if 'high' in data.columns else data['close'].iloc[-20:].max()
        low_20d = data['low'].iloc[-20:].min() if 'low' in data.columns else data['close'].iloc[-20:].min()
        
        if high_20d > low_20d:
            relative_position = (current_price - low_20d) / (high_20d - low_20d)
            
            # 低吸策略：越靠近低点分数越高
            if relative_position <= 0.15:
                position_score = 60  # 极低位，最佳买入
                details['position'] = '极低位(最佳买入)'
            elif relative_position <= 0.25:
                position_score = 55
                details['position'] = '低位区间(0-25%)'
            elif relative_position <= 0.35:
                position_score = 50
                details['position'] = '偏低区间(25-35%)'
            elif relative_position <= 0.50:
                position_score = 40
                details['position'] = '中间区间(35-50%)'
            elif relative_position <= 0.65:
                position_score = 25
                details['position'] = '中高区间(50-65%)'
            else:
                position_score = 10  # 高位区间，不适合买入
                details['position'] = '高位区间(不建议买入)'
            
            details['relative_position'] = round(relative_position * 100, 1)
        score += position_score
        details['position_score'] = position_score
        
        # 2. 反弹信号 (40分) - 检测是否开始反弹
        rebound_score = 0
        
        # 计算近期最低点
        recent_low = data['close'].iloc[-10:].min()
        recent_low_idx = data['close'].iloc[-10:].idxmin()
        
        # 当前价格相对近期最低点的位置
        if current_price > recent_low:
            rebound_pct = (current_price - recent_low) / recent_low * 100
            
            # 检测反弹信号
            if 0.1 <= rebound_pct <= 0.5:
                rebound_score = 40  # 刚开始反弹，最佳时机
                details['rebound'] = f'开始反弹(+{rebound_pct:.2f}%)'
            elif 0.5 < rebound_pct <= 1.0:
                rebound_score = 35
                details['rebound'] = f'小幅反弹(+{rebound_pct:.2f}%)'
            elif 1.0 < rebound_pct <= 2.0:
                rebound_score = 25
                details['rebound'] = f'反弹中(+{rebound_pct:.2f}%)'
            elif rebound_pct > 2.0:
                rebound_score = 15
                details['rebound'] = f'已反弹较多(+{rebound_pct:.2f}%)'
            else:
                rebound_score = 30  # 在最低点附近
                details['rebound'] = '接近最低点'
        else:
            rebound_score = 35  # 在最低点
            details['rebound'] = '处于近期最低点'
        
        # 检测价格是否企稳（连续上涨）
        if len(data) >= 3:
            if current_price > prev_price > data['close'].iloc[-3]:
                rebound_score = min(40, rebound_score + 10)
                details['stabilizing'] = '连续两次上涨，企稳信号'
        
        score += rebound_score
        details['rebound_score'] = rebound_score
        
        return min(100, score), details
    
    def calculate_signal_strength(self, data: pd.DataFrame) -> SignalStrength:
        """
        计算综合信号强度 - 偏向低吸策略
        
        Returns:
            SignalStrength对象，包含详细评分
        """
        # 计算各维度得分
        ma_score, ma_details = self._calculate_ma_score(data)
        rsi_score, rsi_details = self._calculate_rsi_score(data)
        macd_score, macd_details = self._calculate_macd_score(data)
        trend_score, trend_details = self._calculate_trend_score(data)
        position_score, position_details = self._calculate_position_score(data)
        
        # 加权综合得分 - 偏向低吸策略
        # 位置和RSI权重更高（更适合判断低位）
        weights = {
            'ma': 0.15,        # MA指标
            'rsi': 0.25,       # RSI超卖指标(重要)
            'macd': 0.15,      # MACD指标
            'trend': 0.20,     # 趋势/企稳确认
            'position': 0.25   # 价格位置(重要)
        }
        
        total_score = (
            ma_score * weights['ma'] +
            rsi_score * weights['rsi'] +
            macd_score * weights['macd'] +
            trend_score * weights['trend'] +
            position_score * weights['position']
        )
        
        # 确定强度等级
        if total_score >= 80:
            level = '极强'
        elif total_score >= 65:
            level = '强'
        elif total_score >= 50:
            level = '中等'
        elif total_score >= 35:
            level = '弱'
        else:
            level = '极弱'
        
        return SignalStrength(
            total_score=round(total_score, 1),
            level=level,
            ma_score=round(ma_score, 1),
            rsi_score=round(rsi_score, 1),
            macd_score=round(macd_score, 1),
            trend_score=round(trend_score, 1),
            position_score=round(position_score, 1),
            details={
                'ma': ma_details,
                'rsi': rsi_details,
                'macd': macd_details,
                'trend': trend_details,
                'position': position_details,
                'weights': weights
            }
        )
    
    def calculate_ma(self, data: pd.DataFrame, period: int = None) -> pd.Series:
        """
        计算移动平均线
        
        Args:
            data: 包含'close'列的DataFrame
            period: MA周期，默认使用配置值
        
        Returns:
            MA序列
        """
        period = period or self.ma_period
        if len(data) < period:
            return pd.Series(dtype=float)
        
        return data['close'].rolling(window=period).mean()
    
    def calculate_rsi(self, data: pd.DataFrame, period: int = None) -> pd.Series:
        """
        计算RSI相对强弱指数
        
        RSI = 100 - (100 / (1 + RS))
        RS = 平均涨幅 / 平均跌幅
        
        Args:
            data: 包含'close'列的DataFrame
            period: RSI周期，默认使用配置值
        
        Returns:
            RSI序列
        """
        period = period or self.rsi_period
        if len(data) < period + 1:
            return pd.Series(dtype=float)
        
        delta = data['close'].diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算MACD指标
        
        DIF = EMA(fast) - EMA(slow)
        DEA = EMA(DIF, signal)
        MACD柱 = 2 * (DIF - DEA)
        
        Args:
            data: 包含'close'列的DataFrame
        
        Returns:
            (DIF, DEA, MACD柱) 三元组
        """
        if len(data) < self.macd_slow:
            return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
        
        close = data['close']
        
        # 计算EMA
        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        
        # DIF线
        dif = ema_fast - ema_slow
        
        # DEA线(信号线)
        dea = dif.ewm(span=self.macd_signal, adjust=False).mean()
        
        # MACD柱
        macd_hist = 2 * (dif - dea)
        
        return dif, dea, macd_hist
    
    def check_ma_signal(self, data: pd.DataFrame) -> Tuple[bool, str]:
        """
        检查MA买入信号: 价格上穿MA均线
        
        Returns:
            (是否触发, 原因描述)
        """
        if len(data) < self.ma_period + 1:
            return False, "数据不足"
        
        ma = self.calculate_ma(data)
        if ma.empty or len(ma) < 2:
            return False, "MA计算失败"
        
        current_price = data['close'].iloc[-1]
        prev_price = data['close'].iloc[-2]
        current_ma = ma.iloc[-1]
        prev_ma = ma.iloc[-2]
        
        # 价格从下方穿越MA(金叉)
        if prev_price < prev_ma and current_price > current_ma:
            return True, f"价格({current_price:.2f})上穿MA{self.ma_period}({current_ma:.2f})"
        
        # 价格在MA上方且MA上升
        if current_price > current_ma and current_ma > prev_ma:
            return True, f"价格在MA{self.ma_period}上方，均线上升趋势"
        
        return False, f"价格({current_price:.2f})在MA{self.ma_period}({current_ma:.2f})下方"
    
    def check_rsi_signal(self, data: pd.DataFrame) -> Tuple[bool, str]:
        """
        检查RSI买入信号: RSI处于超卖区域(<30)
        
        Returns:
            (是否触发, 原因描述)
        """
        rsi = self.calculate_rsi(data)
        if rsi.empty:
            return False, "RSI计算失败"
        
        current_rsi = rsi.iloc[-1]
        
        if pd.isna(current_rsi):
            return False, "RSI数据无效"
        
        if current_rsi < self.rsi_oversold:
            return True, f"RSI({current_rsi:.1f})处于超卖区域(<{self.rsi_oversold})"
        
        # RSI从超卖区域回升
        if len(rsi) >= 2:
            prev_rsi = rsi.iloc[-2]
            if not pd.isna(prev_rsi) and prev_rsi < self.rsi_oversold <= current_rsi:
                return True, f"RSI从超卖区域回升({prev_rsi:.1f}->{current_rsi:.1f})"
        
        return False, f"RSI({current_rsi:.1f})在正常范围"
    
    def check_macd_signal(self, data: pd.DataFrame) -> Tuple[bool, str]:
        """
        检查MACD买入信号: DIF上穿DEA形成金叉
        
        Returns:
            (是否触发, 原因描述)
        """
        dif, dea, macd_hist = self.calculate_macd(data)
        if dif.empty or len(dif) < 2:
            return False, "MACD计算失败"
        
        current_dif = dif.iloc[-1]
        prev_dif = dif.iloc[-2]
        current_dea = dea.iloc[-1]
        prev_dea = dea.iloc[-2]
        
        if pd.isna(current_dif) or pd.isna(current_dea):
            return False, "MACD数据无效"
        
        # DIF上穿DEA(金叉)
        if prev_dif < prev_dea and current_dif > current_dea:
            return True, f"MACD金叉: DIF({current_dif:.4f})上穿DEA({current_dea:.4f})"
        
        # DIF和DEA都在上升
        if current_dif > prev_dif and current_dea > prev_dea and current_dif > current_dea:
            return True, f"MACD多头趋势: DIF({current_dif:.4f})>DEA({current_dea:.4f})"
        
        return False, f"MACD未形成金叉: DIF({current_dif:.4f}), DEA({current_dea:.4f})"
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        综合三种指标生成买入信号
        
        Args:
            data: 历史价格DataFrame
        
        Returns:
            Signal对象，无信号时返回None
        """
        if data.empty or len(data) < self.macd_slow:
            logger.warning(f"数据量不足(需要至少{self.macd_slow}条记录)")
            return None
        
        # 计数器递增，定期垃圾回收
        self._calc_count += 1
        if self._calc_count % self._gc_interval == 0:
            gc.collect()
        
        current_price = data['close'].iloc[-1]
        reasons = []
        signals_triggered = 0
        
        # 检查各指标信号
        ma_signal, ma_reason = self.check_ma_signal(data)
        rsi_signal, rsi_reason = self.check_rsi_signal(data)
        macd_signal, macd_reason = self.check_macd_signal(data)
        
        if ma_signal:
            signals_triggered += 1
            reasons.append(f"[MA] {ma_reason}")
        
        if rsi_signal:
            signals_triggered += 1
            reasons.append(f"[RSI] {rsi_reason}")
        
        if macd_signal:
            signals_triggered += 1
            reasons.append(f"[MACD] {macd_reason}")
        
        # 计算指标详情
        ma = self.calculate_ma(data)
        rsi = self.calculate_rsi(data)
        dif, dea, macd_hist = self.calculate_macd(data)
        
        indicators = {
            'ma': ma.iloc[-1] if not ma.empty else None,
            'rsi': rsi.iloc[-1] if not rsi.empty else None,
            'macd_dif': dif.iloc[-1] if not dif.empty else None,
            'macd_dea': dea.iloc[-1] if not dea.empty else None,
            'macd_hist': macd_hist.iloc[-1] if not macd_hist.empty else None,
        }
        
        # 计算详细信号强度
        strength_detail = self.calculate_signal_strength(data)
        
        # 判断是否满足买入条件
        # 条件1: 满足最少指标数量
        # 条件2: 强度评分达到阈值
        conditions_met = signals_triggered >= self.min_conditions
        strength_met = strength_detail.total_score >= self.min_strength_score
        
        if conditions_met and strength_met:
            # 将综合评分映射到1-5的强度等级
            if strength_detail.total_score >= 80:
                strength_level = 5
            elif strength_detail.total_score >= 65:
                strength_level = 4
            elif strength_detail.total_score >= 50:
                strength_level = 3
            elif strength_detail.total_score >= 35:
                strength_level = 2
            else:
                strength_level = 1
            
            signal = Signal(
                timestamp=datetime.now(),
                signal_type='BUY',
                strength=strength_level,
                strength_detail=strength_detail,
                price=current_price,
                reasons=reasons,
                indicators=indicators
            )
            
            logger.info(
                f"生成买入信号: 等级{strength_level}({strength_detail.level}), "
                f"综合评分{strength_detail.total_score}, 价格{current_price}"
            )
            logger.info(
                f"  各维度得分 - MA:{strength_detail.ma_score} RSI:{strength_detail.rsi_score} "
                f"MACD:{strength_detail.macd_score} 趋势:{strength_detail.trend_score} "
                f"位置:{strength_detail.position_score}"
            )
            return signal
        
        logger.debug(
            f"未触发买入信号: 条件{signals_triggered}/{self.min_conditions}, "
            f"强度{strength_detail.total_score}/{self.min_strength_score}"
        )
        return None
    
    def get_analysis_summary(self, data: pd.DataFrame) -> Dict:
        """获取当前分析摘要"""
        if data.empty:
            return {}
        
        ma = self.calculate_ma(data)
        rsi = self.calculate_rsi(data)
        dif, dea, macd_hist = self.calculate_macd(data)
        
        return {
            'current_price': data['close'].iloc[-1] if not data.empty else None,
            'ma': ma.iloc[-1] if not ma.empty else None,
            'rsi': rsi.iloc[-1] if not rsi.empty else None,
            'macd': {
                'dif': dif.iloc[-1] if not dif.empty else None,
                'dea': dea.iloc[-1] if not dea.empty else None,
                'hist': macd_hist.iloc[-1] if not macd_hist.empty else None
            },
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 模拟数据
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1min')
    np.random.seed(42)
    prices = 2000 + np.cumsum(np.random.randn(100) * 2)
    
    df = pd.DataFrame({
        'close': prices,
        'open': prices - 1,
        'high': prices + 2,
        'low': prices - 2
    }, index=dates)
    
    config = {
        'ma_period': 20,
        'ma_short_period': 5,
        'ma_long_period': 60,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_extreme_oversold': 20,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'min_conditions': 2,
        'min_strength_score': 40
    }
    
    generator = SignalGenerator(config)
    
    # 计算详细强度
    strength = generator.calculate_signal_strength(df)
    print("=" * 60)
    print("买入强度详细分析")
    print("=" * 60)
    print(f"\n【综合评分】: {strength.total_score}/100 ({strength.level})")
    print(f"\n【各维度得分】:")
    print(f"  - MA均线得分:   {strength.ma_score}/100")
    print(f"  - RSI得分:      {strength.rsi_score}/100")
    print(f"  - MACD得分:     {strength.macd_score}/100")
    print(f"  - 趋势确认得分: {strength.trend_score}/100")
    print(f"  - 价格位置得分: {strength.position_score}/100")
    
    print(f"\n【详细分析】:")
    for key, detail in strength.details.items():
        if key != 'weights' and isinstance(detail, dict):
            print(f"\n  {key.upper()}指标:")
            for k, v in detail.items():
                if not k.endswith('_score'):
                    print(f"    - {k}: {v}")
    
    # 生成信号
    signal = generator.generate_signal(df)
    
    print("\n" + "=" * 60)
    if signal:
        print(f"[OK] 买入信号触发!")
        print(f"   信号等级: {signal.strength}/5 ({signal.strength_detail.level})")
        print(f"   综合评分: {signal.strength_detail.total_score}")
        print(f"   当前价格: {signal.price:.2f}")
        print(f"\n   触发原因:")
        for reason in signal.reasons:
            print(f"     {reason}")
    else:
        print("[X] 未触发买入信号")
        print(f"   当前强度评分: {strength.total_score}")
    print("=" * 60)
