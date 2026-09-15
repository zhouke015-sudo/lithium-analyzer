# -*- coding: utf-8 -*-
import akshare as ak
import time
import warnings
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import random
import os

warnings.filterwarnings('ignore')

# ===================== 参数配置 =====================
REQUEST_INTERVAL = 0.5
RETRY_TIMES = 3
CACHE_EXPIRE = 60
CHECK_INTERVAL = 60  # 检测间隔（秒）
PRICE_OFFSET_RATIO = 0.003

# ===================== 品种映射表 =====================
AKSHARE_SYMBOL_MAP = {
    'c': '玉米', 'cs': '玉米淀粉', 'rm': '菜粕', 'm': '豆粕', 'y': '豆油',
    'p': '棕榈', 'a': '豆一', 'b': '豆二', 'jd': '鸡蛋', 'cf': '棉花',
    'sr': '白糖', 'oi': '菜油', 'ap': '鲜苹果', 'cj': '红枣', 'pk': '花生',
    'cy': '棉纱', 'lh': '生猪', 'sp': '纸浆', 'op': '胶版印刷纸期货', 'lg': '原木',
    'l': '塑料', 'pp': 'PP', 'v': 'PVC', 'ta': 'PTA', 'eg': '乙二醇',
    'ma': '郑醇', 'fu': '燃油', 'eb': '苯乙烯', 'br': '丁二烯橡胶', 'pf': '短纤',
    'pr': '瓶级聚酯切片', 'px': '二甲苯', 'pl': '丙烯', 'bz': '纯苯', 'sh': '烧碱',
    'ur': '尿素', 'sa': '纯碱', 'fg': '玻璃', 'rb': '螺纹钢', 'hc': '热轧卷板',
    'i': '铁矿石', 'jm': '焦煤', 'j': '焦炭', 'ss': '不锈钢', 'bu': '沥青',
    'cu': '沪铜', 'bc': '国际铜', 'al': '沪铝', 'zn': '沪锌', 'pb': '沪铅',
    'ni': '沪镍', 'sn': '沪锡', 'si': '工业硅', 'ao': '氧化铝', 'au': '黄金',
    'ag': '白银', 'pt': '铂', 'pd': '钯', 'sc': '原油', 'lu': '低硫燃料油',
    'pg': '液化石油气', 'if': '沪深300指数期货', 'ic': '中证500指数期货',
    'im': '中证1000股指期货', 'ih': '上证50指数期货', 'ts': '2年期国债期货',
    'tf': '5年期国债期货', 't': '10年期国债期货', 'tl': '10年期国债期货',
    'ps': '多晶硅', 'lc': '碳酸锂', 'ru': '橡胶', 'nr': '20号胶',
    'ec': '集运指数(欧线)期货', 'sf': '硅铁', 'sm': '锰硅',
}

# 连续合约映射（用于获取历史数据）
CONTINUOUS_CONTRACT_MAP = {
    'c': 'C0', 'cs': 'CS0', 'rm': 'RM0', 'm': 'M0', 'y': 'Y0', 'p': 'P0',
    'a': 'A0', 'b': 'B0', 'jd': 'JD0', 'cf': 'CF0', 'sr': 'SR0', 'oi': 'OI0',
    'ap': 'AP0', 'cj': 'CJ0', 'pk': 'PK0', 'cy': 'CY0', 'lh': 'LH0', 'sp': 'SP0',
    'op': 'OP0', 'lg': 'LG0', 'l': 'L0', 'pp': 'PP0', 'v': 'V0', 'ta': 'TA0',
    'eg': 'EG0', 'ma': 'MA0', 'fu': 'FU0', 'eb': 'EB0', 'br': 'BR0', 'pf': 'PF0',
    'pr': 'PR0', 'px': 'PX0', 'pl': 'PL0', 'bz': 'BZ0', 'sh': 'SH0', 'ur': 'UR0',
    'sa': 'SA0', 'fg': 'FG0', 'rb': 'RB0', 'hc': 'HC0', 'i': 'I0', 'jm': 'JM0',
    'j': 'J0', 'ss': 'SS0', 'bu': 'BU0', 'cu': 'CU0', 'bc': 'BC0', 'al': 'AL0',
    'zn': 'ZN0', 'pb': 'PB0', 'ni': 'NI0', 'sn': 'SN0', 'si': 'SI0', 'ao': 'AO0',
    'au': 'AU0', 'ag': 'AG0', 'pt': 'PT0', 'pd': 'PD0', 'sc': 'SC0', 'lu': 'LU0',
    'pg': 'PG0', 'if': 'IF0', 'ic': 'IC0', 'im': 'IM0', 'ih': 'IH0', 'ts': 'TS0',
    'tf': 'TF0', 't': 'T0', 'tl': 'TL0', 'ps': 'PS0', 'lc': 'LC0', 'ru': 'RU0',
    'nr': 'NR', 'sf': 'SF0', 'sm': 'SM0', 'ec': 'EC0'
}

# ===================== 现货价格映射 =====================
SPOT_PRICE_MAP = {}


def load_spot_prices():
    """加载现货价格表"""
    global SPOT_PRICE_MAP

    # 尝试多个可能的文件名
    possible_files = ['现货价格表.xlsx', '现货价格表.csv', '现货价格表.txt']
    spot_file = None

    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    for filename in possible_files:
        filepath = os.path.join(script_dir, filename)
        if os.path.exists(filepath):
            spot_file = filepath
            break

    if spot_file is None:
        print("⚠️ 未找到现货价格表文件（尝试: 现货价格表.xlsx, 现货价格表.csv, 现货价格表.txt）")
        return False

    try:
        if spot_file.endswith('.xlsx'):
            df = pd.read_excel(spot_file)
        elif spot_file.endswith('.csv'):
            df = pd.read_csv(spot_file)
        else:
            try:
                df = pd.read_csv(spot_file, sep='\t')
            except:
                df = pd.read_csv(spot_file, sep=',')

        if '代码' in df.columns and '现货价格' in df.columns:
            for _, row in df.iterrows():
                code = str(row['代码']).strip().upper()
                price = float(row['现货价格'])
                SPOT_PRICE_MAP[code] = price
            print(f"✅ 成功加载现货价格数据，共 {len(SPOT_PRICE_MAP)} 个品种")
            return True
        elif '品种' in df.columns and '价格' in df.columns:
            for _, row in df.iterrows():
                code = str(row['品种']).strip().upper()
                price = float(row['价格'])
                SPOT_PRICE_MAP[code] = price
            print(f"✅ 成功加载现货价格数据，共 {len(SPOT_PRICE_MAP)} 个品种")
            return True
        elif '名称' in df.columns and '现货价格' in df.columns:
            for _, row in df.iterrows():
                code = str(row['名称']).strip().upper()
                price = float(row['现货价格'])
                SPOT_PRICE_MAP[code] = price
            print(f"✅ 成功加载现货价格数据，共 {len(SPOT_PRICE_MAP)} 个品种")
            return True
        else:
            print(f"❌ 现货价格表格式错误，需要包含 '代码' 和 '现货价格' 列")
            print(f"   当前列: {list(df.columns)}")
            return False

    except Exception as e:
        print(f"❌ 加载现货价格表失败: {str(e)}")
        return False


def get_spot_price(code):
    """获取现货价格"""
    return SPOT_PRICE_MAP.get(code.upper(), None)


def safe_request(func, *args, **kwargs):
    """安全请求函数，处理重试"""
    for i in range(RETRY_TIMES):
        try:
            time.sleep(REQUEST_INTERVAL + random.uniform(0.2, 0.6))
            result = func(*args, **kwargs)
            if result is None or (isinstance(result, pd.DataFrame) and result.empty):
                raise ValueError("接口返回空")
            return result
        except Exception as e:
            if i == RETRY_TIMES - 1:
                raise e
            time.sleep(REQUEST_INTERVAL * 2)
    return None


# ===================== 支撑位/阻力位计算函数 =====================
def get_local_low_points_with_volume(df_1m):
    """获取局部低点及其成交量"""
    lows = df_1m["low"].dropna().values
    volumes = df_1m["volume"].dropna().values
    local_lows, local_vols = [], []
    n = len(lows)
    for i in range(2, n - 2):
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
            local_lows.append(lows[i])
            local_vols.append(volumes[i])
    return local_lows, local_vols


def get_local_high_points_with_volume(df_1m):
    """获取局部高点及其成交量"""
    highs = df_1m["high"].dropna().values
    volumes = df_1m["volume"].dropna().values
    local_highs, local_vols = [], []
    n = len(highs)
    for i in range(2, n - 2):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
            local_highs.append(highs[i])
            local_vols.append(volumes[i])
    return local_highs, local_vols


def calculate_weighted_support_resistance(df_1min_all):
    """
    计算成交量加权支撑位和阻力位
    从第一个代码中提取的计算逻辑
    """
    local_lows, low_vols = get_local_low_points_with_volume(df_1min_all)
    local_highs, high_vols = get_local_high_points_with_volume(df_1min_all)

    core_support = None
    if local_lows and low_vols and sum(low_vols) > 0:
        core_support = sum(p * v for p, v in zip(local_lows, low_vols)) / sum(low_vols)

    core_resist = None
    if local_highs and high_vols and sum(high_vols) > 0:
        core_resist = sum(p * v for p, v in zip(local_highs, high_vols)) / sum(high_vols)

    return core_support, core_resist


def get_trading_start_date() -> datetime:
    """获取交易开始时间"""
    now = datetime.now()
    current_weekday = now.weekday()
    current_hour = now.hour

    if current_weekday == 4 and current_hour >= 21:
        days_back = 0
    elif current_weekday == 5:
        days_back = 1
    elif current_weekday == 6:
        days_back = 2
    elif current_weekday == 0 and current_hour < 21:
        days_back = 3
    else:
        days_back = 1 if current_hour < 21 else 0

    if days_back == 0:
        start_date = now.date()
    else:
        start_date = now.date() - timedelta(days=days_back)

    while start_date.weekday() >= 5:
        start_date -= timedelta(days=1)

    return datetime(start_date.year, start_date.month, start_date.day, 21, 0, 0)


def get_kline(contract_code, period="1"):
    """获取K线数据"""
    try:
        df = safe_request(ak.futures_zh_minute_sina, symbol=contract_code, period=period)
        if df is None or df.empty:
            return None

        if 'datetime' not in df.columns:
            if '时间' in df.columns:
                df = df.rename(columns={
                    '时间': 'datetime', '开盘': 'open', '最高': 'high',
                    '最低': 'low', '收盘': 'close', '成交量': 'volume', '持仓量': 'hold'
                })
            else:
                df = df.rename(columns={df.columns[0]: 'datetime'})

        df["datetime"] = pd.to_datetime(df["datetime"])
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        start_dt = get_trading_start_date()
        df_filtered = df[df["datetime"] >= start_dt].copy()
        df_filtered = df_filtered[df_filtered["datetime"] <= datetime.now()].copy()

        if df_filtered.empty:
            return None

        return df_filtered
    except Exception as e:
        return None


def get_realtime_data(contract_code):
    """获取实时数据"""
    try:
        # 提取品种代码（去掉数字部分）
        import re
        fut_code = re.sub(r'[0-9]', '', contract_code).lower()

        if fut_code not in AKSHARE_SYMBOL_MAP:
            print(f"⚠️ 品种 {fut_code} 不在映射表中")
            return None

        akshare_name = AKSHARE_SYMBOL_MAP[fut_code]
        df = safe_request(ak.futures_zh_realtime, symbol=akshare_name)
        if df is None or df.empty:
            return None

        # 查找指定合约
        found_row = None
        for idx, row in df.iterrows():
            if str(row.get('symbol', '')) == contract_code.upper():
                found_row = row
                break

        if found_row is None:
            # 如果找不到精确匹配，按成交量排序取第一个
            if 'volume' in df.columns:
                df = df.sort_values('volume', ascending=False)
                found_row = df.iloc[0]
            else:
                found_row = df.iloc[0]

        if found_row is None:
            return None

        realtime_data = {
            'price': float(found_row.get('trade', 0)),
            'open': float(found_row.get('open', 0)),
            'high': float(found_row.get('high', 0)),
            'low': float(found_row.get('low', 0)),
            'volume': int(found_row.get('volume', 0)),
            'position': int(found_row.get('position', 0)),
            'yesterday_close': float(found_row.get('preclose', 0)),
            'symbol': str(found_row.get('symbol', '')),
            'name': str(found_row.get('name', ''))
        }

        return realtime_data
    except Exception as e:
        print(f"⚠️ 获取实时数据失败: {e}")
        return None


def get_historical_kline(contract_code, days=5):
    """获取历史日线数据用于计算支撑阻力"""
    try:
        df = safe_request(ak.futures_zh_daily_sina, symbol=contract_code)
        if df is None or df.empty:
            return None
        df = df.tail(days).copy()
        return df
    except Exception as e:
        return None


def main():
    print("=" * 80)
    print("【期货支撑/阻力位监控 + 基差分析】")
    print("=" * 80)
    print("功能说明：")
    print("  1. 手动输入品种合约（如 LC2609）")
    print("  2. 计算阻力位和动态结算价")
    print("  3. 实时价在阻力位以上且动态结算价以上 → 空头开仓信号")
    print("  4. 自动加载现货价格计算基差")
    print("=" * 80)

    # 加载现货价格表
    print("\n【加载现货价格】")
    print("-" * 80)
    load_success = load_spot_prices()
    if load_success:
        print(f"✅ 成功加载 {len(SPOT_PRICE_MAP)} 个品种的现货价格")
    else:
        print("⚠️ 未加载现货价格，基差分析将不可用")
    print("-" * 80)

    # 用户输入合约
    contract_input = input("\n请输入品种合约（如 LC2609）：").strip().upper()
    if not contract_input:
        print("❌ 合约代码不能为空")
        return

    # 提取品种代码
    import re
    fut_code = re.sub(r'[0-9]', '', contract_input).lower()

    print(f"\n监控合约: {contract_input}")
    print(f"品种代码: {fut_code}")

    # 获取现货价格
    spot_price = get_spot_price(fut_code.upper())
    if spot_price is not None:
        print(f"现货价格: {spot_price:.2f}")
    else:
        print("⚠️ 未找到该品种的现货价格")

    print("\n开始监控... (按 Ctrl+C 停止)\n")
    print("-" * 80)

    # 缓存K线数据
    kline_cache = None
    last_fetch_time = 0

    # 持仓状态
    has_position = False
    entry_price = 0

    try:
        while True:
            now = datetime.now()

            # 每60秒获取一次K线数据
            if time.time() - last_fetch_time >= 60:
                df_kline = get_kline(contract_input, "1")
                if df_kline is not None and not df_kline.empty:
                    kline_cache = df_kline
                    last_fetch_time = time.time()
                    print(f"[{now.strftime('%H:%M:%S')}] 更新K线数据，共 {len(df_kline)} 根")
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] 获取K线数据失败")

            if kline_cache is None or kline_cache.empty:
                time.sleep(CHECK_INTERVAL)
                continue

            # 获取实时数据
            realtime_data = get_realtime_data(contract_input)
            if realtime_data is None:
                time.sleep(CHECK_INTERVAL)
                continue

            current_price = realtime_data['price']
            today_open = realtime_data['open']
            today_high = realtime_data['high']
            today_low = realtime_data['low']

            if current_price <= 0:
                time.sleep(CHECK_INTERVAL)
                continue

            # ===== 计算支撑位和阻力位 =====
            core_support, core_resist = calculate_weighted_support_resistance(kline_cache)

            # ===== 计算动态结算价 =====
            # 动态结算价 = (最高 + 最低 + 开盘 + 实时) / 4
            dynamic_settlement = (today_high + today_low + today_open + current_price) / 4

            # 打印当前状态
            print(f"\n{'=' * 60}")
            print(f"时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"合约: {contract_input}")
            print(f"实时价: {current_price:.2f}")
            print(f"开盘: {today_open:.2f}  最高: {today_high:.2f}  最低: {today_low:.2f}")
            print(f"动态结算价: {dynamic_settlement:.2f}")
            print(f"阻力位: {core_resist:.2f}" if core_resist is not None else "阻力位: 计算中...")
            print(f"支撑位: {core_support:.2f}" if core_support is not None else "支撑位: 计算中...")
            print("-" * 60)

            # ===== 基差计算 =====
            basis_msg = ""
            if spot_price is not None and spot_price > 0 and current_price > 0:
                basis_ratio = (spot_price - current_price) / current_price
                basis_pct = basis_ratio * 100
                print(f"现货价: {spot_price:.2f}")
                print(f"基差比率: {basis_pct:.2f}%")

                if basis_ratio > 0.05:
                    basis_msg = "⚠️ 期货弱预期，请结合基本面增大开仓手数"
                elif basis_ratio < -0.05:
                    basis_msg = "⚠️ 期货强预期，请结合基本面减少开仓手数"
                else:
                    basis_msg = "✓ 基差正常"
                print(f"基差信号: {basis_msg}")

            # ===== 空头开仓信号判断 =====
            # 条件1: 实时价在阻力位以上
            # 条件2: 实时价在动态结算价以上
            if core_resist is not None:
                price_above_resistance = current_price > core_resist
                price_above_settlement = current_price > dynamic_settlement

                print(f"价格 > 阻力位: {price_above_resistance}")
                print(f"价格 > 动态结算价: {price_above_settlement}")

                if price_above_resistance and price_above_settlement:
                    print("\n" + "!" * 60)
                    print("🔴 【空头开仓信号】")
                    print(f"  合约: {contract_input}")
                    print(f"  实时价: {current_price:.2f}")
                    print(f"  阻力位: {core_resist:.2f}")
                    print(f"  动态结算价: {dynamic_settlement:.2f}")
                    if basis_msg and basis_msg.startswith("⚠️"):
                        print(f"  {basis_msg}")
                    print("!" * 60)

                    # 记录持仓状态
                    if not has_position:
                        has_position = True
                        entry_price = current_price
                        print(f"\n📊 已记录开仓价: {entry_price:.2f}")
                else:
                    if has_position:
                        # 检查是否应该平仓
                        if current_price < core_resist or current_price < dynamic_settlement:
                            print("\n" + "!" * 60)
                            print("🟢 【平仓信号】")
                            print(f"  合约: {contract_input}")
                            print(f"  开仓价: {entry_price:.2f}")
                            print(f"  当前价: {current_price:.2f}")
                            print(f"  盈亏: {(current_price - entry_price):.2f} 点")
                            print("!" * 60)
                            has_position = False
                            entry_price = 0
            else:
                print("⏳ 等待足够K线数据计算阻力位...")

            print("=" * 60)

            # 等待下一次检测
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n=== 程序手动停止 ===")
    except Exception as e:
        print(f"\n=== 程序异常退出: {str(e)} ===")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()