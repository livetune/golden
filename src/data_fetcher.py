"""
数据获取模块 - 获取上海黄金交易所Au9999实时价格
支持数据源: 东方财富
"""
import requests
import logging
import gc
import weakref
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
from collections import deque
import time

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """数据源枚举"""
    CNGOLD = "cngold"         # 金投网(jijinhao)
    EASTMONEY = "eastmoney"   # 东方财富


@dataclass
class GoldPrice:
    """黄金价格数据结构"""
    timestamp: datetime
    price: float           # 当前价格 (元/克)
    open_price: float      # 今开
    high: float            # 最高
    low: float             # 最低
    change: float          # 涨跌额
    change_percent: float  # 涨跌幅(%)
    name: str = "Au9999"
    source: str = "eastmoney"
    unit: str = "元/克"


class DataFetcher:
    """数据获取类 - 上海黄金交易所Au9999"""
    
    # 金投网接口 - 上金所Au9999
    CNGOLD_URL = "https://api.jijinhao.com/quoteCenter/realTime.htm"
    CNGOLD_AU9999_CODE = "JO_71"  # Au9999品种代码
    
    # 东方财富接口 - 上金所Au9999
    EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/stock/get"
    
    # 数据源列表（金投网优先，东方财富备用）
    SOURCE_PRIORITY = [DataSource.CNGOLD, DataSource.EASTMONEY]
    
    # 默认最大历史记录数
    DEFAULT_MAX_HISTORY = 500
    
    def __init__(self, config: dict):
        self.timeout = config.get('timeout', 10)
        self.retry_times = config.get('retry_times', 3)
        self._max_history = config.get('max_history', self.DEFAULT_MAX_HISTORY)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
            'Referer': 'https://quote.eastmoney.com',
            'Accept': 'application/json',
        }
        # 使用deque替代list，自动限制大小，避免内存无限增长
        self._price_history: deque = deque(maxlen=self._max_history)
        self._failed_sources: set = set()
        # 复用requests Session，减少连接开销
        self._session: Optional[requests.Session] = None
        # 添加清理计数器
        self._fetch_count = 0
        self._gc_interval = 100  # 每100次获取执行一次gc
    
    def _get_session(self) -> requests.Session:
        """获取或创建HTTP Session"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.headers)
        return self._session
    
    def _close_session(self):
        """关闭HTTP Session"""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
    
    def fetch_gold_price(self) -> Optional[GoldPrice]:
        """获取当前Au9999价格"""
        self._failed_sources.clear()
        self._fetch_count += 1
        
        # 定期执行垃圾回收
        if self._fetch_count % self._gc_interval == 0:
            gc.collect()
        
        for source in self.SOURCE_PRIORITY:
            if source in self._failed_sources:
                continue
                
            for attempt in range(self.retry_times):
                try:
                    price = self._fetch_from_source(source)
                    if price:
                        self._price_history.append(price)
                        # deque自动管理大小，无需手动截断
                        return price
                except Exception as e:
                    if attempt == self.retry_times - 1:
                        logger.warning(f"获取失败: {e}")
                    time.sleep(1)
            
            self._failed_sources.add(source)
        
        logger.error("数据源不可用")
        return None
    
    def _fetch_from_source(self, source: DataSource) -> Optional[GoldPrice]:
        """从指定数据源获取数据"""
        if source == DataSource.CNGOLD:
            return self._fetch_cngold_au9999()
        elif source == DataSource.EASTMONEY:
            return self._fetch_eastmoney_au9999()
        return None
    
    def _fetch_cngold_au9999(self) -> Optional[GoldPrice]:
        """从金投网(jijinhao)获取上金所Au9999价格"""
        import re
        
        params = {
            'codes': self.CNGOLD_AU9999_CODE,
            '_': str(int(time.time() * 1000))
        }
        
        session = self._get_session()
        response = session.get(
            self.CNGOLD_URL,
            params=params,
            headers={
                **self.headers,
                'Referer': 'https://www.cngold.org/',
            },
            timeout=self.timeout
        )
        
        text = response.text
        # 返回格式: var quote_json = {...}
        match = re.search(r'var\s+quote_json\s*=\s*(\{.*\})', text)
        if not match:
            logger.warning(f"金投网API返回格式异常: {text[:200]}")
            return None
        
        import json
        data = json.loads(match.group(1))
        if not data.get('flag') or self.CNGOLD_AU9999_CODE not in data:
            logger.warning(f"金投网API返回异常: {data}")
            return None
        
        d = data[self.CNGOLD_AU9999_CODE]
        
        current_price = float(d.get('q63', 0))    # 最新价
        open_price = float(d.get('q1', 0))         # 今开
        high = float(d.get('q3', 0))               # 最高
        low = float(d.get('q4', 0))                # 最低
        yesterday_close = float(d.get('q5', 0))    # 昨收
        change = float(d.get('q70', 0))            # 涨跌额
        change_percent = float(d.get('q80', 0))    # 涨跌幅
        
        if current_price <= 0:
            logger.warning(f"金投网返回价格异常: {current_price}")
            return None
        
        return GoldPrice(
            timestamp=datetime.now(),
            price=current_price,
            open_price=open_price,
            high=high,
            low=low,
            change=change,
            change_percent=change_percent,
            name=d.get('showCode', 'Au9999'),
            source="cngold",
            unit=d.get('unit', '元/克')
        )
    
    def _fetch_eastmoney_au9999(self) -> Optional[GoldPrice]:
        """从东方财富获取上金所Au9999价格"""
        params = {
            'secid': '118.AU9999',  # 上海黄金交易所Au9999
            'fields': 'f43,f44,f45,f46,f58,f60,f169,f170'
            # f43=当前价, f44=最高, f45=最低, f46=今开
            # f58=名称, f60=昨收, f169=涨跌额, f170=涨跌幅
        }
        
        session = self._get_session()
        response = session.get(
            self.EASTMONEY_URL, 
            params=params,
            timeout=self.timeout
        )
        
        data = response.json()
        if data.get('rc') != 0 or not data.get('data'):
            logger.warning(f"东方财富API返回异常: {data}")
            return None
        
        d = data['data']
        
        # 东方财富价格单位是分，需要除以100转为元/克
        current_price = d['f43'] / 100
        high = d['f44'] / 100
        low = d['f45'] / 100
        open_price = d['f46'] / 100
        yesterday_close = d['f60'] / 100
        change = d['f169'] / 100
        change_percent = d['f170'] / 100
        
        return GoldPrice(
            timestamp=datetime.now(),
            price=current_price,
            open_price=open_price,
            high=high,
            low=low,
            change=change,
            change_percent=change_percent,
            name=d.get('f58', 'Au9999'),
            source="eastmoney",
            unit="元/克"
        )
    
    def test_all_sources(self) -> dict:
        """测试所有数据源的可用性"""
        results = {}
        for source in self.SOURCE_PRIORITY:
            try:
                start_time = time.time()
                price = self._fetch_from_source(source)
                elapsed = time.time() - start_time
                results[source.value] = {
                    'status': 'ok' if price else 'no_data',
                    'price': price.price if price else None,
                    'unit': price.unit if price else None,
                    'name': price.name if price else None,
                    'latency_ms': round(elapsed * 1000, 2)
                }
            except Exception as e:
                results[source.value] = {
                    'status': 'error',
                    'error': str(e),
                    'price': None
                }
        return results
    
    def get_price_history(self) -> List[GoldPrice]:
        """获取价格历史记录"""
        return list(self._price_history)
    
    def clear_history(self):
        """清空历史记录"""
        self._price_history.clear()
    
    def cleanup(self):
        """清理资源"""
        self._close_session()
        self.clear_history()
        gc.collect()
    
    def __del__(self):
        """析构函数，确保资源被释放"""
        try:
            self._close_session()
        except Exception:
            pass
    
    def get_memory_info(self) -> dict:
        """获取内存使用信息（调试用）"""
        return {
            'history_count': len(self._price_history),
            'max_history': self._max_history,
            'fetch_count': self._fetch_count,
            'session_active': self._session is not None
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("=" * 50)
    print("Shanghai Gold Exchange Au9999")
    print("=" * 50)
    
    config = {'timeout': 10, 'retry_times': 3}
    fetcher = DataFetcher(config)
    
    # 测试数据源
    results = fetcher.test_all_sources()
    for source, info in results.items():
        status = "[OK]" if info['status'] == 'ok' else "[FAIL]"
        price_str = f"{info['price']:.2f}" if info['price'] else "N/A"
        unit = info.get('unit', '')
        latency = f"{info.get('latency_ms', 'N/A')}ms"
        print(f"  {status:8s} {source:12s} | {price_str:10s} {unit:8s} | {latency}")
    
    print("\n" + "=" * 50)
    print("Fetch Au9999 price")
    print("=" * 50)
    
    price = fetcher.fetch_gold_price()
    if price:
        print(f"  Name:    {price.name}")
        print(f"  Price:   {price.price:.2f} {price.unit}")
        print(f"  Open:    {price.open_price:.2f} {price.unit}")
        print(f"  High:    {price.high:.2f} {price.unit}")
        print(f"  Low:     {price.low:.2f} {price.unit}")
        print(f"  Change:  {price.change:+.2f} {price.unit} ({price.change_percent:+.2f}%)")
    else:
        print("  Failed to fetch Au9999 price")
