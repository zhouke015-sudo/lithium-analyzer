# futures_api.py - 手动输入版本
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')


class FuturesAPI:
    """期货数据API - 手动输入版本"""

    def __init__(self):
        self.last_update_time = None
        self.futures_data = None

    def update_futures_data(self, price, open_price=None, high=None, low=None, volume=None, change_pct=None):
        """
        手动更新期货数据
        参数:
            price: 实时价格（必填）
            open: 开盘价（可选）
            high: 最高价（可选）
            low: 最低价（可选）
            volume: 成交量（可选）
            change_pct: 涨跌幅（可选）
        """
        try:
            price = float(price)
            if price <= 0:
                raise ValueError("价格必须大于0")

            self.futures_data = {
                'symbol': 'LC0 (手动输入)',
                'price': price,
                'open': float(open_price) if open_price is not None else price,
                'high': float(high) if high is not None else price,
                'low': float(low) if low is not None else price,
                'volume': int(volume) if volume is not None else 0,
                'position': 0,
                'change_pct': float(change_pct) if change_pct is not None else 0,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_manual': True
            }
            self.last_update_time = datetime.now()
            print(f"✅ 期货数据已更新: {price}")
            return True

        except ValueError as e:
            print(f"❌ 期货数据更新失败: {e}")
            return False

    def get_futures_realtime(self):
        """获取期货实时数据"""
        if self.futures_data is None:
            raise ValueError("请先输入期货价格")
        return self.futures_data

    def get_futures_with_cache(self):
        """获取缓存的期货数据"""
        if self.futures_data is None:
            raise ValueError("请先输入期货价格")
        return self.futures_data

    def has_data(self):
        """检查是否有数据"""
        return self.futures_data is not None