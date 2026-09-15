# data_processor.py
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os

warnings.filterwarnings('ignore')

# ===================== 6个核心指标（历史分位/统计信息使用） =====================
INDICATORS = {
    '澳大利亚锂辉石精矿': {'col': 'H', 'unit': '美元/吨', 'color': '#2E86AB'},
    '电池级碳酸锂': {'col': 'L', 'unit': '元/吨', 'color': '#A23B72'},
    '工业级碳酸锂': {'col': 'M', 'unit': '元/吨', 'color': '#F18F01'},
    '主力合约结算价': {'col': 'O', 'unit': '元/吨', 'color': '#C73E1D'},
    '主力合约仓单': {'col': 'U', 'unit': '手', 'color': '#6A994E'},
    '电池级碳酸锂期现价差': {'col': 'N', 'unit': '元/吨', 'color': '#BC4B51'}
}

# ===================== 4个价格（传导量化使用） =====================
CONDUCTION_PRICES = {
    '澳大利亚锂辉石精矿': {'col': 'H', 'unit': '美元/吨', 'color': '#2E86AB'},
    '电池级碳酸锂': {'col': 'L', 'unit': '元/吨', 'color': '#A23B72'},
    '工业级碳酸锂': {'col': 'M', 'unit': '元/吨', 'color': '#F18F01'},
    '主力合约结算价': {'col': 'O', 'unit': '元/吨', 'color': '#C73E1D'}
}

SHEET_NAMES = {
    '供需平衡表': '供需平衡表',
    '紫金矿业': '紫金矿业',
    '宁德时代': '宁德时代'
}


def col_to_index(col):
    """将Excel列名转换为索引（支持AA, AB等）"""
    result = 0
    for char in col:
        result = result * 26 + (ord(char.upper()) - ord('A') + 1)
    return result - 1


def read_data(file_path, sheet_name='供需平衡表'):
    """
    读取Excel数据（只读取6个核心指标）
    数据从第7行开始（索引7）
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    data_start = 7

    dates = []
    data_dict = {name: [] for name in INDICATORS.keys()}

    for idx in range(data_start, len(df)):
        row = df.iloc[idx]
        date_val = row[0]

        if pd.isna(date_val):
            break

        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime('%Y-%m-%d')
        elif isinstance(date_val, datetime):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val).strip()
            if ' ' in date_str:
                date_str = date_str.split(' ')[0]

        dates.append(date_str)

        for name, config in INDICATORS.items():
            col_idx = col_to_index(config['col'])
            if col_idx < len(row):
                val = row[col_idx]
                if pd.notna(val) and val != '':
                    try:
                        data_dict[name].append(float(val))
                    except:
                        data_dict[name].append(np.nan)
                else:
                    data_dict[name].append(np.nan)
            else:
                data_dict[name].append(np.nan)

    return dates, data_dict


def read_conduction_prices(file_path, sheet_name='供需平衡表'):
    """只读取传导量化所需的4个价格"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    data_start = 7

    dates = []
    data_dict = {name: [] for name in CONDUCTION_PRICES.keys()}

    for idx in range(data_start, len(df)):
        row = df.iloc[idx]
        date_val = row[0]

        if pd.isna(date_val):
            break

        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime('%Y-%m-%d')
        elif isinstance(date_val, datetime):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val).strip()
            if ' ' in date_str:
                date_str = date_str.split(' ')[0]

        dates.append(date_str)

        for name, config in CONDUCTION_PRICES.items():
            col_idx = col_to_index(config['col'])
            if col_idx < len(row):
                val = row[col_idx]
                if pd.notna(val) and val != '':
                    try:
                        data_dict[name].append(float(val))
                    except:
                        data_dict[name].append(np.nan)
                else:
                    data_dict[name].append(np.nan)
            else:
                data_dict[name].append(np.nan)

    return dates, data_dict


def read_sheet_data(file_path, sheet_name, header_row=0):
    """通用读取Excel sheet数据"""
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        return df
    except Exception as e:
        print(f"读取 {sheet_name} 失败: {e}")
        return None


# ===================== 支撑位和阻力位 =====================
def get_local_low_points(data_series, window=2):
    values = data_series.values
    local_lows = []
    n = len(values)
    for i in range(window, n - window):
        is_low = True
        for j in range(1, window + 1):
            if values[i] >= values[i - j] or values[i] >= values[i + j]:
                is_low = False
                break
        if is_low:
            local_lows.append(values[i])
    return local_lows


def get_local_high_points(data_series, window=2):
    values = data_series.values
    local_highs = []
    n = len(values)
    for i in range(window, n - window):
        is_high = True
        for j in range(1, window + 1):
            if values[i] <= values[i - j] or values[i] <= values[i + j]:
                is_high = False
                break
        if is_high:
            local_highs.append(values[i])
    return local_highs


def calculate_weighted_support_resistance(data_series, window=2):
    local_lows = get_local_low_points(data_series, window)
    local_highs = get_local_high_points(data_series, window)
    core_support = np.mean(local_lows) if local_lows else None
    core_resist = np.mean(local_highs) if local_highs else None
    return core_support, core_resist, len(local_lows), len(local_highs)


# ===================== 计算统计指标 =====================
def calculate_stats(data, dates):
    series = pd.Series(data, index=dates)
    valid_data = series.dropna()

    if len(valid_data) < 2:
        return None

    current_price = valid_data.iloc[0]
    current_date = valid_data.index[0]

    week_data = valid_data.iloc[:5] if len(valid_data) >= 5 else valid_data
    week_return = (week_data.iloc[0] - week_data.iloc[-1]) / week_data.iloc[-1] * 100 if len(week_data) > 1 else 0
    week_avg = week_data.mean()

    month_data = valid_data.iloc[:22] if len(valid_data) >= 22 else valid_data
    month_return = (month_data.iloc[0] - month_data.iloc[-1]) / month_data.iloc[-1] * 100 if len(month_data) > 1 else 0
    month_avg = month_data.mean()

    year_data = valid_data.iloc[:252] if len(valid_data) >= 252 else valid_data
    year_return = (year_data.iloc[0] - year_data.iloc[-1]) / year_data.iloc[-1] * 100 if len(year_data) > 1 else 0
    year_avg = year_data.mean()

    def calc_volatility(data_series):
        if len(data_series) < 2:
            return 0
        reversed_data = data_series.iloc[::-1].copy()
        reversed_data = reversed_data.replace(0, 1)
        log_returns = np.log(reversed_data / reversed_data.shift(1))
        log_returns = log_returns.replace([np.inf, -np.inf], np.nan).dropna()
        if len(log_returns) < 2:
            return 0
        return np.std(log_returns) * np.sqrt(252) * 100

    week_vol = calc_volatility(week_data) if len(week_data) >= 5 else 0
    month_vol = calc_volatility(month_data) if len(month_data) >= 22 else 0
    year_vol = calc_volatility(year_data) if len(year_data) >= 252 else 0

    month_support, month_resist, month_low_count, month_high_count = calculate_weighted_support_resistance(month_data, window=2)
    year_support, year_resist, year_low_count, year_high_count = calculate_weighted_support_resistance(valid_data, window=3)

    return {
        'current_price': current_price,
        'current_date': current_date,
        'week_return': week_return,
        'month_return': month_return,
        'year_return': year_return,
        'week_avg': week_avg,
        'month_avg': month_avg,
        'year_avg': year_avg,
        'week_volatility': week_vol,
        'month_volatility': month_vol,
        'year_volatility': year_vol,
        'month_support': month_support,
        'month_resistance': month_resist,
        'month_low_count': month_low_count,
        'month_high_count': month_high_count,
        'year_support': year_support,
        'year_resistance': year_resist,
        'year_low_count': year_low_count,
        'year_high_count': year_high_count,
        'data_count': len(valid_data),
        'min_val': valid_data.min(),
        'max_val': valid_data.max()
    }