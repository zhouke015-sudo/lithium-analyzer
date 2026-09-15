# conduction_quant.py
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import time
import random

warnings.filterwarnings('ignore')


class ConductionQuantCalculator:
    """传导量化计算器"""

    def __init__(self, dates, data_dict):
        """
        初始化计算器
        dates: 日期列表
        data_dict: 六个指标的数据字典
        """
        self.dates = dates
        self.data_dict = data_dict

        # 固定参数
        self.EXCHANGE_RATE = 1  # 汇率（美元转人民币）
        self.CONVERSION_FACTOR = 7  # 转换系数
        self.WEIGHTS = {
            'battery': 0.25,
            'industrial': 0.25,
            'futures': 0.50
        }

        # 计算历史统计
        self.historical_stats = self.calculate_historical_stats()

        # 缓存上次获取的期货数据
        self.last_futures_data = None
        self.last_futures_time = None

    def calculate_historical_stats(self):
        """计算历史数据的比值均值和标准差"""
        # 创建DataFrame
        df = pd.DataFrame({
            'date': self.dates,
            '精矿': self.data_dict['锂辉石精矿'],
            '电池级': self.data_dict['电池级碳酸锂'],
            '工业级': self.data_dict['工业级碳酸锂'],
            '期货': self.data_dict['主力合约结算价']
        })

        # 转换精矿价格为元/吨
        df['精矿_元'] = df['精矿'] * self.EXCHANGE_RATE

        # 计算三个比值
        df['比值_电池级'] = (df['精矿_元'] * self.CONVERSION_FACTOR) / df['电池级']
        df['比值_工业级'] = (df['精矿_元'] * self.CONVERSION_FACTOR) / df['工业级']
        df['比值_期货'] = (df['精矿_元'] * self.CONVERSION_FACTOR) / df['期货']

        # 去除无效数据
        df_clean = df.dropna(subset=['比值_电池级', '比值_工业级', '比值_期货'])

        if len(df_clean) < 10:
            return None

        # 返回统计结果
        return {
            '均值_电池级': df_clean['比值_电池级'].mean(),
            '均值_工业级': df_clean['比值_工业级'].mean(),
            '均值_期货': df_clean['比值_期货'].mean(),
            '标准差_电池级': df_clean['比值_电池级'].std(),
            '标准差_工业级': df_clean['比值_工业级'].std(),
            '标准差_期货': df_clean['比值_期货'].std(),
            '数据量': len(df_clean),
            '最新日期': df_clean['date'].iloc[-1],
        }

    def get_futures_realtime(self):
        """
        获取期货实时价格（模拟数据，实际使用时替换为真实API）
        """
        # 这里使用模拟数据，实际项目中替换为真实API调用
        # 模拟价格在历史价格附近波动
        try:
            # 获取历史期货数据
            futures_data = pd.Series(self.data_dict['主力合约结算价'])
            valid_data = futures_data.dropna()

            if len(valid_data) > 0:
                base_price = valid_data.iloc[0]  # 使用最新价格作为基准
                # 模拟随机波动 ±2%
                change_pct = random.uniform(-0.02, 0.02)
                current_price = base_price * (1 + change_pct)

                # 模拟OHLC
                open_price = current_price * (1 + random.uniform(-0.01, 0.01))
                high_price = max(current_price, open_price) * (1 + random.uniform(0, 0.01))
                low_price = min(current_price, open_price) * (1 - random.uniform(0, 0.01))

                return {
                    'symbol': 'LC0',
                    'price': round(current_price, 2),
                    'open': round(open_price, 2),
                    'high': round(high_price, 2),
                    'low': round(low_price, 2),
                    'volume': random.randint(100000, 500000),
                    'position': random.randint(100000, 300000),
                    'change_pct': round(change_pct * 100, 2),
                    'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception as e:
            pass

        # 如果无法获取，返回模拟数据
        return {
            'symbol': 'LC0',
            'price': 75000 + random.randint(-2000, 2000),
            'open': 75000 + random.randint(-3000, 3000),
            'high': 75000 + random.randint(-1000, 4000),
            'low': 75000 + random.randint(-4000, 1000),
            'volume': random.randint(100000, 500000),
            'position': random.randint(100000, 300000),
            'change_pct': round(random.uniform(-3, 3), 2),
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def calculate_ratio(self, ore_price_usd, carbonate_price):
        """计算比值"""
        ore_price_rmb = ore_price_usd * self.EXCHANGE_RATE
        ratio = (ore_price_rmb * self.CONVERSION_FACTOR) / carbonate_price
        return ratio

    def calculate_zscore(self, current_ratio, mean, std):
        """计算Z-Score"""
        if std is None or std == 0:
            return 0
        return (current_ratio - mean) / std

    def calculate_cdi(self, z_battery, z_industrial, z_futures):
        """计算CDI"""
        cdi = (self.WEIGHTS['battery'] * z_battery +
               self.WEIGHTS['industrial'] * z_industrial +
               self.WEIGHTS['futures'] * z_futures)
        return cdi

    def get_trading_signal(self, cdi):
        """获取交易信号"""
        if cdi > 2.0:
            return {
                'signal': '强烈看多',
                'direction': 'BUY',
                'level': 'strong',
                'description': '整体严重低估（成本高、产品价格低）',
                'action': '多期货或现货'
            }
        elif cdi > 1.5:
            return {
                'signal': '轻度看多',
                'direction': 'BUY',
                'level': 'moderate',
                'description': '轻度低估，可轻仓试多',
                'action': '轻仓试多'
            }
        elif cdi >= -1.5:
            return {
                'signal': '观望',
                'direction': 'NEUTRAL',
                'level': 'neutral',
                'description': '比值处于正常区间',
                'action': '观望'
            }
        elif cdi > -2.0:
            return {
                'signal': '轻度看空',
                'direction': 'SELL',
                'level': 'moderate',
                'description': '轻度高估，可轻仓试空',
                'action': '轻仓试空'
            }
        else:
            return {
                'signal': '强烈看空',
                'direction': 'SELL',
                'level': 'strong',
                'description': '整体严重高估（成本低、产品价格高）',
                'action': '空期货或套保'
            }

    def calculate(self, ore_price, battery_price, industrial_price):
        """
        执行完整计算
        """
        if self.historical_stats is None:
            return None

        # 获取期货实时数据
        futures_data = self.get_futures_realtime()
        if futures_data is None:
            futures_data = {
                'symbol': 'LC0',
                'price': 75000,
                'open': 75000,
                'high': 75000,
                'low': 75000,
                'volume': 0,
                'position': 0,
                'change_pct': 0,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        futures_price = futures_data['price']

        # 计算动态结算价 = (最高+最低+开盘+收盘)/4
        settlement_price = (futures_data['high'] + futures_data['low'] +
                            futures_data['open'] + futures_price) / 4

        # 计算三个比值
        ratio_battery = self.calculate_ratio(ore_price, battery_price)
        ratio_industrial = self.calculate_ratio(ore_price, industrial_price)
        ratio_futures = self.calculate_ratio(ore_price, futures_price)

        # 计算Z-Score
        z_battery = self.calculate_zscore(
            ratio_battery,
            self.historical_stats['均值_电池级'],
            self.historical_stats['标准差_电池级']
        )
        z_industrial = self.calculate_zscore(
            ratio_industrial,
            self.historical_stats['均值_工业级'],
            self.historical_stats['标准差_工业级']
        )
        z_futures = self.calculate_zscore(
            ratio_futures,
            self.historical_stats['均值_期货'],
            self.historical_stats['标准差_期货']
        )

        # 计算CDI
        cdi = self.calculate_cdi(z_battery, z_industrial, z_futures)

        # 获取交易信号
        signal = self.get_trading_signal(cdi)

        # 返回完整结果
        return {
            'datetime': futures_data['datetime'],
            'symbol': futures_data['symbol'],

            # 输入价格
            'ore_price': ore_price,
            'battery_price': battery_price,
            'industrial_price': industrial_price,

            # 期货行情
            'futures_price': futures_price,
            'settlement_price': settlement_price,
            'change_pct': futures_data['change_pct'],
            'volume': futures_data['volume'],
            'position': futures_data['position'],

            # 比值
            'ratio_battery': ratio_battery,
            'ratio_industrial': ratio_industrial,
            'ratio_futures': ratio_futures,

            # 历史均值
            'mean_battery': self.historical_stats['均值_电池级'],
            'mean_industrial': self.historical_stats['均值_工业级'],
            'mean_futures': self.historical_stats['均值_期货'],

            # Z-Score
            'z_battery': z_battery,
            'z_industrial': z_industrial,
            'z_futures': z_futures,

            # CDI
            'cdi': cdi,
            'weight_battery': self.WEIGHTS['battery'],
            'weight_industrial': self.WEIGHTS['industrial'],
            'weight_futures': self.WEIGHTS['futures'],

            # 交易信号
            'signal': signal['signal'],
            'direction': signal['direction'],
            'action': signal['action'],
        }