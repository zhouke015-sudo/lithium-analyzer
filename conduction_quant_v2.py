# conduction_quant_v2.py
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')


class ConductionQuantV2:
    """传导量化 - 四价格Z-Score模型"""

    def __init__(self, dates, data_dict):
        self.dates = dates
        self.data_dict = data_dict

        self.price_keys = ['澳大利亚锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约结算价']

        self.WEIGHTS = {
            '澳大利亚锂辉石精矿': 0.25,
            '电池级碳酸锂': 0.25,
            '工业级碳酸锂': 0.25,
            '主力合约结算价': 0.25
        }

        self.historical_stats = self.calculate_historical_stats()
        self.futures_data = None

    def calculate_historical_stats(self):
        df = pd.DataFrame({
            'date': self.dates,
            '澳大利亚锂辉石精矿': self.data_dict['澳大利亚锂辉石精矿'],
            '电池级碳酸锂': self.data_dict['电池级碳酸锂'],
            '工业级碳酸锂': self.data_dict['工业级碳酸锂'],
            '主力合约结算价': self.data_dict['主力合约结算价']
        })

        df_clean = df.dropna(subset=['澳大利亚锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约结算价'])

        if len(df_clean) < 10:
            return None

        return {
            '均值_澳大利亚锂辉石精矿': df_clean['澳大利亚锂辉石精矿'].mean(),
            '均值_电池级碳酸锂': df_clean['电池级碳酸锂'].mean(),
            '均值_工业级碳酸锂': df_clean['工业级碳酸锂'].mean(),
            '均值_主力合约结算价': df_clean['主力合约结算价'].mean(),
            '标准差_澳大利亚锂辉石精矿': df_clean['澳大利亚锂辉石精矿'].std(),
            '标准差_电池级碳酸锂': df_clean['电池级碳酸锂'].std(),
            '标准差_工业级碳酸锂': df_clean['工业级碳酸锂'].std(),
            '标准差_主力合约结算价': df_clean['主力合约结算价'].std(),
            '数据量': len(df_clean),
            '最新日期': df_clean['date'].iloc[-1],
        }

    def set_futures_data(self, futures_data):
        self.futures_data = futures_data

    def calculate_zscore(self, current_price, mean, std):
        if std is None or std == 0:
            return 0
        return (current_price - mean) / std

    def calculate_cdi(self, z_ore, z_battery, z_industrial, z_futures):
        cdi = (self.WEIGHTS['澳大利亚锂辉石精矿'] * z_ore +
               self.WEIGHTS['电池级碳酸锂'] * z_battery +
               self.WEIGHTS['工业级碳酸锂'] * z_industrial +
               self.WEIGHTS['主力合约结算价'] * z_futures)
        return cdi

    def get_trading_signal(self, cdi):
        if cdi > 2.0:
            return {'signal': '强烈看空', 'direction': 'SELL', 'level': 'strong',
                    'description': '四个价格整体严重高估', 'action': '空期货或套保'}
        elif cdi > 1.5:
            return {'signal': '轻度看空', 'direction': 'SELL', 'level': 'moderate',
                    'description': '四个价格整体轻度高估', 'action': '轻仓试空'}
        elif cdi >= -1.5:
            return {'signal': '观望', 'direction': 'NEUTRAL', 'level': 'neutral',
                    'description': '四个价格处于正常区间', 'action': '观望'}
        elif cdi > -2.0:
            return {'signal': '轻度看多', 'direction': 'BUY', 'level': 'moderate',
                    'description': '四个价格整体轻度低估', 'action': '轻仓试多'}
        else:
            return {'signal': '强烈看多', 'direction': 'BUY', 'level': 'strong',
                    'description': '四个价格整体严重低估', 'action': '多期货或现货'}

    def calculate(self, ore_price, battery_price, industrial_price, futures_price):
        if self.historical_stats is None:
            return None

        z_ore = self.calculate_zscore(ore_price,
                                       self.historical_stats['均值_澳大利亚锂辉石精矿'],
                                       self.historical_stats['标准差_澳大利亚锂辉石精矿'])
        z_battery = self.calculate_zscore(battery_price,
                                           self.historical_stats['均值_电池级碳酸锂'],
                                           self.historical_stats['标准差_电池级碳酸锂'])
        z_industrial = self.calculate_zscore(industrial_price,
                                              self.historical_stats['均值_工业级碳酸锂'],
                                              self.historical_stats['标准差_工业级碳酸锂'])
        z_futures = self.calculate_zscore(futures_price,
                                           self.historical_stats['均值_主力合约结算价'],
                                           self.historical_stats['标准差_主力合约结算价'])

        cdi = self.calculate_cdi(z_ore, z_battery, z_industrial, z_futures)
        signal = self.get_trading_signal(cdi)

        settlement_price = 0
        symbol = 'LC0'
        change_pct = 0
        volume = 0

        if self.futures_data:
            settlement_price = (self.futures_data.get('high', 0) +
                                self.futures_data.get('low', 0) +
                                self.futures_data.get('open', 0) +
                                futures_price) / 4
            symbol = self.futures_data.get('symbol', 'LC0')
            change_pct = self.futures_data.get('change_pct', 0)
            volume = self.futures_data.get('volume', 0)

        df = pd.DataFrame({
            '澳大利亚锂辉石精矿': self.data_dict['澳大利亚锂辉石精矿'],
            '电池级碳酸锂': self.data_dict['电池级碳酸锂'],
            '工业级碳酸锂': self.data_dict['工业级碳酸锂'],
            '主力合约结算价': self.data_dict['主力合约结算价']
        })
        df_clean = df.dropna()

        def calc_percentile(series, value):
            if len(series) == 0:
                return 50
            sorted_vals = np.sort(series.values)
            idx = np.searchsorted(sorted_vals, value)
            return (idx / len(sorted_vals)) * 100

        return {
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'ore_price': ore_price,
            'battery_price': battery_price,
            'industrial_price': industrial_price,
            'futures_price': futures_price,
            'settlement_price': settlement_price,
            'change_pct': change_pct,
            'volume': volume,
            'mean_ore': self.historical_stats['均值_澳大利亚锂辉石精矿'],
            'mean_battery': self.historical_stats['均值_电池级碳酸锂'],
            'mean_industrial': self.historical_stats['均值_工业级碳酸锂'],
            'mean_futures': self.historical_stats['均值_主力合约结算价'],
            'std_ore': self.historical_stats['标准差_澳大利亚锂辉石精矿'],
            'std_battery': self.historical_stats['标准差_电池级碳酸锂'],
            'std_industrial': self.historical_stats['标准差_工业级碳酸锂'],
            'std_futures': self.historical_stats['标准差_主力合约结算价'],
            'z_ore': z_ore,
            'z_battery': z_battery,
            'z_industrial': z_industrial,
            'z_futures': z_futures,
            'percentile_ore': calc_percentile(df_clean['澳大利亚锂辉石精矿'], ore_price),
            'percentile_battery': calc_percentile(df_clean['电池级碳酸锂'], battery_price),
            'percentile_industrial': calc_percentile(df_clean['工业级碳酸锂'], industrial_price),
            'percentile_futures': calc_percentile(df_clean['主力合约结算价'], futures_price),
            'cdi': cdi,
            'weight_ore': self.WEIGHTS['澳大利亚锂辉石精矿'],
            'weight_battery': self.WEIGHTS['电池级碳酸锂'],
            'weight_industrial': self.WEIGHTS['工业级碳酸锂'],
            'weight_futures': self.WEIGHTS['主力合约结算价'],
            'signal': signal['signal'],
            'direction': signal['direction'],
            'action': signal['action'],
        }