"""
价格波动监控算法模块 - 基于当日高低价的简单波动通知
"""
import logging
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PriceSignal:
    """价格波动信号"""
    timestamp: datetime
    signal_type: str        # 'RISE' 涨, 'DROP' 跌
    price: float            # 当前价格
    today_high: float       # 当日最高价
    today_low: float        # 当日最低价
    change: float           # 波动幅度（正数）
    reference_price: float  # 参考价格（基准点）
    reasons: list = field(default_factory=list)


class PriceAlgorithm:
    """
    简单价格波动监控算法
    
    逻辑：
    - 记录当天的最高价和最低价
    - 当价格相比最高价跌超过阈值时，触发跌幅通知
    - 当价格相比最低价涨超过阈值时，触发涨幅通知
    - 触发通知后，更新已通知基准价格，避免重复通知，同时能捕捉持续单边行情
    - 跨天自动重置
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: 算法配置
                - threshold: 波动阈值，默认5（元/克）
        """
        self.threshold = config.get('threshold', 5)
        
        # 当日状态
        self._current_date: Optional[date] = None
        self._today_high: Optional[float] = None
        self._today_low: Optional[float] = None
        
        # 已通知基准价格（用于避免重复通知，同时捕捉持续行情）
        self._notified_high: Optional[float] = None  # 上次触发跌通知时的基准高点
        self._notified_low: Optional[float] = None    # 上次触发涨通知时的基准低点
        
        # 统计
        self._update_count = 0
        
        logger.info(f"价格算法初始化 | 阈值: {self.threshold}")
    
    def update(self, price: float) -> Optional[PriceSignal]:
        """
        更新价格，判断是否触发通知
        
        Args:
            price: 当前价格
            
        Returns:
            PriceSignal 或 None
        """
        now = datetime.now()
        today = now.date()
        
        # 跨天重置
        if self._current_date != today:
            self._reset(today)
            logger.info(f"新交易日 {today}，状态已重置")
        
        self._update_count += 1
        
        # 更新当日高低价
        if self._today_high is None or price > self._today_high:
            self._today_high = price
            # 新高点同时作为跌通知的基准
            self._notified_high = price
            logger.debug(f"更新当日最高价: {price:.2f}")
        
        if self._today_low is None or price < self._today_low:
            self._today_low = price
            # 新低点同时作为涨通知的基准
            self._notified_low = price
            logger.debug(f"更新当日最低价: {price:.2f}")
        
        # 检查跌幅：当前价格相比基准高点跌了多少
        drop = self._notified_high - price
        if drop >= self.threshold:
            signal = PriceSignal(
                timestamp=now,
                signal_type='DROP',
                price=price,
                today_high=self._today_high,
                today_low=self._today_low,
                change=drop,
                reference_price=self._notified_high,
                reasons=[
                    f"价格从 {self._notified_high:.2f} 跌至 {price:.2f}，跌幅 {drop:.2f}",
                    f"当日最高: {self._today_high:.2f}，当日最低: {self._today_low:.2f}"
                ]
            )
            # 更新基准：以当前价格为新的跌通知基准高点
            self._notified_high = price
            logger.info(f"触发跌幅通知 | 跌幅: {drop:.2f} | 价格: {price:.2f}")
            return signal
        
        # 检查涨幅：当前价格相比基准低点涨了多少
        rise = price - self._notified_low
        if rise >= self.threshold:
            signal = PriceSignal(
                timestamp=now,
                signal_type='RISE',
                price=price,
                today_high=self._today_high,
                today_low=self._today_low,
                change=rise,
                reference_price=self._notified_low,
                reasons=[
                    f"价格从 {self._notified_low:.2f} 涨至 {price:.2f}，涨幅 {rise:.2f}",
                    f"当日最高: {self._today_high:.2f}，当日最低: {self._today_low:.2f}"
                ]
            )
            # 更新基准：以当前价格为新的涨通知基准低点
            self._notified_low = price
            logger.info(f"触发涨幅通知 | 涨幅: {rise:.2f} | 价格: {price:.2f}")
            return signal
        
        return None
    
    def _reset(self, today: date):
        """重置当日数据"""
        self._current_date = today
        self._today_high = None
        self._today_low = None
        self._notified_high = None
        self._notified_low = None
        self._update_count = 0
    
    def get_status(self) -> dict:
        """获取算法当前状态"""
        return {
            'date': str(self._current_date) if self._current_date else None,
            'today_high': self._today_high,
            'today_low': self._today_low,
            'notified_high': self._notified_high,
            'notified_low': self._notified_low,
            'threshold': self.threshold,
            'update_count': self._update_count,
        }
