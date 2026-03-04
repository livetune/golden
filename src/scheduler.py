"""
定时调度模块 - 每分钟执行价格获取和信号分析
"""
import schedule
import time
import logging
import gc
import signal
import sys
import threading
from datetime import datetime
from typing import Callable, Optional
from contextlib import contextmanager

from .data_fetcher import DataFetcher, GoldPrice
from .price_algorithm import PriceAlgorithm, PriceSignal
from .email_notifier import EmailNotifier

logger = logging.getLogger(__name__)


class Scheduler:
    """定时调度器 - 管理金价监控任务"""
    
    def __init__(self, config: dict):
        """
        初始化调度器
        
        Args:
            config: 完整配置字典
        """
        self.config = config
        self.interval = config.get('api', {}).get('interval', 60)  # 默认60秒
        
        # 初始化各模块
        self.data_fetcher = DataFetcher(config.get('api', {}))
        self.price_algorithm = PriceAlgorithm(config.get('algorithm', {}))
        self.email_notifier = EmailNotifier(config.get('email', {}))
        
        # 信号冷却配置
        self._last_signal_time: Optional[datetime] = None
        self._signal_cooldown = config.get('algorithm', {}).get('cooldown', 600)
        
        # 运行状态
        self._running = False
        self._job = None
        self._lock = threading.Lock()
        
        # 内存管理配置
        self._gc_interval = config.get('memory', {}).get('gc_interval', 60)  # GC间隔（秒）
        self._last_gc_time = time.time()
        self._task_count = 0
        self._max_task_errors = config.get('memory', {}).get('max_task_errors', 10)
        self._consecutive_errors = 0
        
        # 注册信号处理器
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """设置系统信号处理器，确保优雅退出"""
        def signal_handler(signum, frame):
            logger.info(f"收到退出信号 {signum}")
            self.stop()
            sys.exit(0)
        
        # Windows 和 Unix 兼容的信号处理
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (AttributeError, ValueError):
            # Windows 可能不支持某些信号
            pass
    
    def _periodic_gc(self):
        """定期执行垃圾回收"""
        current_time = time.time()
        if current_time - self._last_gc_time >= self._gc_interval:
            gc.collect()
            self._last_gc_time = current_time
            logger.debug(f"执行垃圾回收，任务计数: {self._task_count}")
    
    def _monitor_task(self):
        """监控任务 - 获取价格、分析信号、发送通知"""
        with self._lock:
            self._task_count += 1
        
        try:
            # 定期垃圾回收
            self._periodic_gc()
            
            # 1. 获取当前金价
            price = self.data_fetcher.fetch_gold_price()
            if not price:
                logger.warning("获取金价失败")
                self._consecutive_errors += 1
                self._check_error_threshold()
                return
            
            # 成功获取数据，重置错误计数
            self._consecutive_errors = 0
            
            logger.info(f"Au9999: {price.price:.2f} {price.unit} ({price.change_percent:+.2f}%)")
            
            # 2. 价格波动算法判断
            signal = self.price_algorithm.update(price.price)
            
            if signal:
                type_desc = "涨" if signal.signal_type == 'RISE' else "跌"
                logger.info(
                    f"[{signal.signal_type}] 价格{type_desc}幅通知! "
                    f"波动:{signal.change:.2f} 价格:{signal.price:.2f}"
                )
                
                if self._check_signal_cooldown():
                    if self._send_price_notification(signal):
                        self._last_signal_time = datetime.now()
                        logger.info("邮件已发送")
                    else:
                        logger.warning("邮件发送失败")
                else:
                    logger.debug("信号冷却中")
                
        except MemoryError:
            logger.error("内存不足，执行紧急清理")
            self._emergency_cleanup()
        except Exception as e:
            logger.error(f"监控异常: {e}")
            self._consecutive_errors += 1
            self._check_error_threshold()
    
    def _check_error_threshold(self):
        """检查连续错误是否超过阈值"""
        if self._consecutive_errors >= self._max_task_errors:
            logger.error(f"连续错误次数达到阈值 {self._max_task_errors}，执行清理")
            self._emergency_cleanup()
            self._consecutive_errors = 0
    
    def _emergency_cleanup(self):
        """紧急内存清理"""
        logger.warning("执行紧急内存清理")
        try:
            # 清理数据获取器的历史记录
            self.data_fetcher.clear_history()
            # 强制垃圾回收
            gc.collect()
            gc.collect()
        except Exception as e:
            logger.error(f"紧急清理失败: {e}")
    
    def _check_signal_cooldown(self) -> bool:
        """检查信号是否已过冷却期"""
        if not self._last_signal_time:
            return True
        
        elapsed = (datetime.now() - self._last_signal_time).total_seconds()
        return elapsed >= self._signal_cooldown
    
    def _send_price_notification(self, signal: PriceSignal) -> bool:
        """
        发送价格波动通知邮件
        
        Args:
            signal: PriceSignal 对象
            
        Returns:
            是否发送成功
        """
        type_desc = "上涨" if signal.signal_type == 'RISE' else "下跌"
        type_color = "#e53935" if signal.signal_type == 'RISE' else "#43a047"
        arrow = "↑" if signal.signal_type == 'RISE' else "↓"
        
        subject = f"黄金价格{type_desc}提醒 {arrow}{signal.change:.2f} 元/克"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; padding: 20px;">
            <div style="max-width: 500px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #FFD700, #FFA500); color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
                    <h1 style="margin: 0; font-size: 22px;">黄金价格{type_desc}提醒</h1>
                </div>
                <div style="padding: 20px;">
                    <div style="background: #fff8e1; border-left: 4px solid {type_color}; padding: 15px; margin: 15px 0;">
                        <div style="font-size: 14px; color: #666;">当前价格</div>
                        <div style="font-size: 32px; color: {type_color}; font-weight: bold;">
                            {signal.price:.2f} <span style="font-size: 14px;">元/克</span>
                        </div>
                        <div style="font-size: 16px; color: {type_color}; margin-top: 5px;">
                            {arrow} {type_desc} {signal.change:.2f} 元/克
                        </div>
                    </div>
                    
                    <div style="background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 15px 0;">
                        <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                            <span style="color: #666;">当日最高价</span>
                            <span style="font-weight: bold; color: #e53935;">{signal.today_high:.2f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                            <span style="color: #666;">当日最低价</span>
                            <span style="font-weight: bold; color: #43a047;">{signal.today_low:.2f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                            <span style="color: #666;">参考基准价</span>
                            <span style="font-weight: bold;">{signal.reference_price:.2f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                            <span style="color: #666;">波动阈值</span>
                            <span style="font-weight: bold;">{self.price_algorithm.threshold} 元/克</span>
                        </div>
                    </div>
                    
                    <p style="color: #ff9800; font-size: 13px;">* 此提醒仅供参考，投资有风险，决策需谨慎。</p>
                </div>
                <div style="text-align: center; padding: 15px; color: #999; font-size: 12px; border-top: 1px solid #eee;">
                    <p>通知时间: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>黄金价格监控系统</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.email_notifier._send_email(subject, html, is_html=True)
    
    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行中")
            return
        
        logger.info(f"监控启动 | 间隔:{self.interval}s")
        
        # 立即执行一次
        self._monitor_task()
        
        # 设置定时任务
        schedule.every(self.interval).seconds.do(self._monitor_task)
        
        self._running = True
        
        try:
            while self._running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """停止调度器"""
        self._running = False
        schedule.clear()
        # 清理资源
        self._cleanup()
        logger.info("监控已停止")
    
    def _cleanup(self):
        """清理所有资源"""
        try:
            # 清理数据获取器
            if hasattr(self, 'data_fetcher') and self.data_fetcher:
                self.data_fetcher.cleanup()
            
            # 清理邮件通知器
            if hasattr(self, 'email_notifier') and self.email_notifier:
                self.email_notifier.cleanup()
            
            # 强制垃圾回收
            gc.collect()
            logger.debug("资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
    
    def run_once(self):
        """执行一次监控任务（用于测试）"""
        self._monitor_task()
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        memory_info = {}
        if hasattr(self, 'data_fetcher') and self.data_fetcher:
            memory_info = self.data_fetcher.get_memory_info()
        
        algorithm_status = {}
        if hasattr(self, 'price_algorithm') and self.price_algorithm:
            algorithm_status = self.price_algorithm.get_status()
        
        return {
            'running': self._running,
            'interval': self.interval,
            'last_signal_time': self._last_signal_time.isoformat() if self._last_signal_time else None,
            'signal_cooldown': self._signal_cooldown,
            'task_count': self._task_count,
            'consecutive_errors': self._consecutive_errors,
            'algorithm': algorithm_status,
            'memory_info': memory_info
        }
    
    def __del__(self):
        """析构函数，确保资源被释放"""
        try:
            self._cleanup()
        except Exception:
            pass
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出，确保资源清理"""
        self.stop()
        return False


if __name__ == "__main__":
    # 测试代码
    import yaml
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 加载配置
    config = {
        'api': {
            'source': 'sina',
            'interval': 60,
            'timeout': 10,
            'retry_times': 3
        },
        'algorithm': {
            'threshold': 5,
            'cooldown': 600
        },
        'email': {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 465,
            'use_ssl': True,
            'sender': 'your_qq@qq.com',
            'password': 'your_auth_code',
            'receivers': ['target@qq.com']
        }
    }
    
    scheduler = Scheduler(config)
    
    # 测试单次执行
    print("执行单次监控任务...")
    scheduler.run_once()
    
    print("\n调度器状态:")
    print(scheduler.get_status())
