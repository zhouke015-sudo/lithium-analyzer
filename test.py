# -*- coding: utf-8 -*-
"""
碳酸锂价格偏离度回测系统（四价格Z-Score模型）- 全数据版本
功能：
1. 使用全部历史数据计算四个价格的均值和标准差
2. 使用全部数据进行回测
3. 计算四个价格的Z-Score，等权得到CDI
4. CDI > 2.0 表示价格整体高估 → 做空
5. CDI < -2.0 表示价格整体低估 → 做多
6. 统计1日、1周、1月的胜率和平均涨跌幅
"""

import pandas as pd
import numpy as np
import warnings
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib

warnings.filterwarnings('ignore')

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC', 'Heiti SC']
matplotlib.rcParams['axes.unicode_minus'] = False

# ===================== 配置参数 =====================
FILE_PATH = 'SMM_碳酸锂日度.xlsx'
SHEET_NAME = '价格数据'

# CDI阈值
CDI_THRESHOLD_BUY = -1.5   # CDI < -2.0 做多（价格整体被低估）
CDI_THRESHOLD_SELL = 1.5   # CDI > 2.0 做空（价格整体被高估）


# ===================== 数据读取模块 =====================
def read_excel_data(file_path, sheet_name):
    """
    从Excel读取六个指标的历史数据
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    data_start = 7

    dates = []
    data_dict = {
        '锂辉石精矿': [],
        '电池级碳酸锂': [],
        '工业级碳酸锂': [],
        '主力合约结算价': [],
        '主力合约仓单': [],
        '期现基差': []
    }

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

        col_indices = {'锂辉石精矿': 1, '电池级碳酸锂': 2, '工业级碳酸锂': 3,
                       '主力合约结算价': 4, '主力合约仓单': 5, '期现基差': 6}

        for name, col_idx in col_indices.items():
            val = row[col_idx]
            if pd.notna(val) and val != '':
                try:
                    data_dict[name].append(float(val))
                except:
                    data_dict[name].append(np.nan)
            else:
                data_dict[name].append(np.nan)

    # 反转数据，让日期从旧到新
    dates.reverse()
    for name in data_dict.keys():
        data_dict[name].reverse()

    return dates, data_dict


# ===================== 统计计算模块 =====================
def calculate_stats(df):
    """
    计算四个价格的均值和标准差（使用全部数据）
    """
    df_clean = df.dropna(subset=['锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约结算价'])

    stats = {
        '均值_锂辉石精矿': df_clean['锂辉石精矿'].mean(),
        '均值_电池级碳酸锂': df_clean['电池级碳酸锂'].mean(),
        '均值_工业级碳酸锂': df_clean['工业级碳酸锂'].mean(),
        '均值_主力合约结算价': df_clean['主力合约结算价'].mean(),
        '标准差_锂辉石精矿': df_clean['锂辉石精矿'].std(),
        '标准差_电池级碳酸锂': df_clean['电池级碳酸锂'].std(),
        '标准差_工业级碳酸锂': df_clean['工业级碳酸锂'].std(),
        '标准差_主力合约结算价': df_clean['主力合约结算价'].std(),
        '数据量': len(df_clean)
    }
    return stats


def calculate_zscore(price, mean, std):
    """计算Z-Score"""
    if std is None or std == 0:
        return 0
    return (price - mean) / std


def calculate_cdi(z_ore, z_battery, z_industrial, z_futures):
    """
    计算综合偏离指数CDI（四个价格等权）
    CDI > 0: 价格整体高于历史均值（高估）
    CDI < 0: 价格整体低于历史均值（低估）
    """
    return 0.25 * z_ore + 0.25 * z_battery + 0.25 * z_industrial + 0.25 * z_futures


# ===================== 回测引擎 =====================
def run_backtest(df_full, stats):
    """
    运行回测（全部数据）
    CDI < -2.0 → 做多（价格整体被低估）
    CDI > 2.0 → 做空（价格整体被高估）
    """
    trades = []

    # 获取完整数据
    test_data = df_full.dropna(subset=['锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约结算价'])

    if len(test_data) == 0:
        print("⚠️ 无有效数据")
        return None, None

    print(f"\n📊 全数据量: {len(test_data)} 个交易日")
    print(f"   日期范围: {test_data['date'].iloc[0]} ~ {test_data['date'].iloc[-1]}")

    # 遍历每一天
    for i in range(len(test_data)):
        row = test_data.iloc[i]
        current_date = row['date']

        # 计算四个价格的Z-Score
        z_ore = calculate_zscore(row['锂辉石精矿'], stats['均值_锂辉石精矿'], stats['标准差_锂辉石精矿'])
        z_battery = calculate_zscore(row['电池级碳酸锂'], stats['均值_电池级碳酸锂'], stats['标准差_电池级碳酸锂'])
        z_industrial = calculate_zscore(row['工业级碳酸锂'], stats['均值_工业级碳酸锂'], stats['标准差_工业级碳酸锂'])
        z_futures = calculate_zscore(row['主力合约结算价'], stats['均值_主力合约结算价'], stats['标准差_主力合约结算价'])

        cdi = calculate_cdi(z_ore, z_battery, z_industrial, z_futures)

        # 获取当前结算价
        entry_price = row['主力合约结算价']

        # 检查未来1天、1周、1月的价格
        future_1d = None
        future_1w = None
        future_1m = None

        if i + 1 < len(test_data):
            future_1d = test_data.iloc[i + 1]['主力合约结算价']
        if i + 5 < len(test_data):
            future_1w = test_data.iloc[i + 5]['主力合约结算价']
        if i + 22 < len(test_data):
            future_1m = test_data.iloc[i + 22]['主力合约结算价']

        # ===== 判断信号 =====
        # CDI < -2.0 → 价格整体被低估 → 做多
        # CDI > 2.0 → 价格整体被高估 → 做空
        signal = None
        if cdi < CDI_THRESHOLD_BUY:
            signal = 'BUY'
        elif cdi > CDI_THRESHOLD_SELL:
            signal = 'SELL'

        if signal is not None and entry_price > 0:
            trade = {
                'date': current_date,
                'signal': signal,
                'cdi': cdi,
                'entry_price': entry_price,
                'z_ore': z_ore,
                'z_battery': z_battery,
                'z_industrial': z_industrial,
                'z_futures': z_futures,
                'price_1d': future_1d,
                'price_1w': future_1w,
                'price_1m': future_1m,
                'return_1d': None,
                'return_1w': None,
                'return_1m': None,
                'win_1d': None,
                'win_1w': None,
                'win_1m': None
            }

            # 计算收益率
            if future_1d is not None and future_1d > 0:
                if signal == 'BUY':
                    trade['return_1d'] = (future_1d - entry_price) / entry_price * 100
                    trade['win_1d'] = future_1d > entry_price
                else:  # SELL
                    trade['return_1d'] = (entry_price - future_1d) / entry_price * 100
                    trade['win_1d'] = future_1d < entry_price

            if future_1w is not None and future_1w > 0:
                if signal == 'BUY':
                    trade['return_1w'] = (future_1w - entry_price) / entry_price * 100
                    trade['win_1w'] = future_1w > entry_price
                else:
                    trade['return_1w'] = (entry_price - future_1w) / entry_price * 100
                    trade['win_1w'] = future_1w < entry_price

            if future_1m is not None and future_1m > 0:
                if signal == 'BUY':
                    trade['return_1m'] = (future_1m - entry_price) / entry_price * 100
                    trade['win_1m'] = future_1m > entry_price
                else:
                    trade['return_1m'] = (entry_price - future_1m) / entry_price * 100
                    trade['win_1m'] = future_1m < entry_price

            trades.append(trade)

    return trades, test_data


# ===================== 统计分析 =====================
def analyze_trades(trades):
    """
    分析交易结果
    """
    if not trades:
        print("⚠️ 无交易记录")
        return None

    df_trades = pd.DataFrame(trades)

    # 按信号分组
    buy_trades = df_trades[df_trades['signal'] == 'BUY']
    sell_trades = df_trades[df_trades['signal'] == 'SELL']

    results = {
        'total_trades': len(trades),
        'buy_trades': len(buy_trades),
        'sell_trades': len(sell_trades),
        'buy': {},
        'sell': {},
        'all': {}
    }

    # 分析所有交易
    for period, period_name in [('1d', '1日'), ('1w', '1周'), ('1m', '1月')]:
        results['all'][period_name] = analyze_period(df_trades, period)

    # 分析做多交易
    if len(buy_trades) > 0:
        for period, period_name in [('1d', '1日'), ('1w', '1周'), ('1m', '1月')]:
            results['buy'][period_name] = analyze_period(buy_trades, period)
    else:
        for period_name in ['1日', '1周', '1月']:
            results['buy'][period_name] = {'count': 0, 'win_rate': 0, 'avg_return': 0}

    # 分析做空交易
    if len(sell_trades) > 0:
        for period, period_name in [('1d', '1日'), ('1w', '1周'), ('1m', '1月')]:
            results['sell'][period_name] = analyze_period(sell_trades, period)
    else:
        for period_name in ['1日', '1周', '1月']:
            results['sell'][period_name] = {'count': 0, 'win_rate': 0, 'avg_return': 0}

    return results, df_trades


def analyze_period(df, period_col):
    """分析单个周期"""
    # 过滤有效数据
    valid = df[df[f'return_{period_col}'].notna()]

    if len(valid) == 0:
        return {'count': 0, 'win_rate': 0, 'avg_return': 0}

    win_count = valid[f'win_{period_col}'].sum()
    total_count = len(valid)
    avg_return = valid[f'return_{period_col}'].mean()

    return {
        'count': total_count,
        'win_rate': win_count / total_count * 100 if total_count > 0 else 0,
        'avg_return': avg_return
    }


# ===================== 打印结果 =====================
def print_results(results, df_trades, stats):
    """打印回测结果"""
    if results is None:
        return

    print("\n" + "=" * 80)
    print("📊 回测结果汇总（全数据）")
    print("=" * 80)

    print(f"\n📈 总体交易统计:")
    print(f"   总交易次数: {results['total_trades']}")
    print(f"   做多次数 (CDI < -2.0，价格低估): {results['buy_trades']}")
    print(f"   做空次数 (CDI > 2.0，价格高估): {results['sell_trades']}")

    print("\n" + "-" * 80)
    print("📊 所有交易统计")
    print("-" * 80)
    print(f"{'周期':<8} {'交易次数':<10} {'胜率':<12} {'平均收益率':<12}")
    print("-" * 40)
    for period_name in ['1日', '1周', '1月']:
        data = results['all'][period_name]
        print(f"{period_name:<8} {data['count']:<10} {data['win_rate']:>6.2f}%     {data['avg_return']:>+8.2f}%")

    print("\n" + "-" * 80)
    print("📊 做多交易统计 (CDI < -2.0，价格整体被低估)")
    print("-" * 80)
    print(f"{'周期':<8} {'交易次数':<10} {'胜率':<12} {'平均收益率':<12}")
    print("-" * 40)
    for period_name in ['1日', '1周', '1月']:
        data = results['buy'][period_name]
        print(f"{period_name:<8} {data['count']:<10} {data['win_rate']:>6.2f}%     {data['avg_return']:>+8.2f}%")

    print("\n" + "-" * 80)
    print("📊 做空交易统计 (CDI > 2.0，价格整体被高估)")
    print("-" * 80)
    print(f"{'周期':<8} {'交易次数':<10} {'胜率':<12} {'平均收益率':<12}")
    print("-" * 40)
    for period_name in ['1日', '1周', '1月']:
        data = results['sell'][period_name]
        print(f"{period_name:<8} {data['count']:<10} {data['win_rate']:>6.2f}%     {data['avg_return']:>+8.2f}%")

    # 打印详细交易记录
    print("\n" + "=" * 80)
    print("📋 详细交易记录")
    print("=" * 80)

    if df_trades is not None and len(df_trades) > 0:
        # 选择要显示的列
        display_cols = ['date', 'signal', 'cdi', 'entry_price', 'return_1d', 'return_1w', 'return_1m']
        display_df = df_trades[display_cols].copy()
        display_df.columns = ['日期', '方向', 'CDI', '开仓价', '1日收益%', '1周收益%', '1月收益%']

        # 格式化
        display_df['CDI'] = display_df['CDI'].map(lambda x: f'{x:+.4f}')
        display_df['开仓价'] = display_df['开仓价'].map(lambda x: f'{x:.2f}')

        for col in ['1日收益%', '1周收益%', '1月收益%']:
            display_df[col] = display_df[col].map(lambda x: f'{x:+.2f}%' if pd.notna(x) else 'N/A')

        print(display_df.to_string(index=False))

        # 保存到CSV
        df_trades.to_csv('回测交易记录_全数据_四价格模型.csv', index=False, encoding='utf-8-sig')
        print(f"\n📁 交易记录已保存: 回测交易记录_全数据_四价格模型.csv")


# ===================== 绘制图表 =====================
def plot_results(df_full, df_trades, stats):
    """绘制回测图表"""
    if df_full is None or len(df_full) == 0:
        return

    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    # 图1: CDI走势及信号标记
    ax1 = axes[0]
    dates = pd.to_datetime(df_full['date'])
    cdi_values = df_full['cdi']

    ax1.plot(dates, cdi_values, color='#2E86AB', linewidth=1.5, label='CDI')
    ax1.axhline(y=2.0, color='red', linestyle='--', linewidth=1, label='做空阈值 (+2.0) 高估')
    ax1.axhline(y=-2.0, color='green', linestyle='--', linewidth=1, label='做多阈值 (-2.0) 低估')
    ax1.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)

    # 标记交易信号
    if df_trades is not None and len(df_trades) > 0:
        for idx, trade in df_trades.iterrows():
            trade_date = pd.to_datetime(trade['date'])
            if trade['signal'] == 'BUY':
                ax1.scatter(trade_date, -2.5, color='green', s=80, marker='^', zorder=5, label='做多' if idx == 0 else "")
            else:
                ax1.scatter(trade_date, 2.5, color='red', s=80, marker='v', zorder=5, label='做空' if idx == 0 else "")

    ax1.set_xlabel('日期')
    ax1.set_ylabel('CDI')
    ax1.set_title('CDI走势与交易信号 (CDI > 2.0 高估做空 | CDI < -2.0 低估做多)')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # 图2: 价格走势
    ax2 = axes[1]
    ax2.plot(dates, df_full['主力合约结算价'], color='#A23B72', linewidth=1.5, label='期货结算价')
    ax2.set_xlabel('日期')
    ax2.set_ylabel('价格 (元/吨)')
    ax2.set_title('碳酸锂主力合约结算价走势')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # 图3: 四个价格的Z-Score走势
    ax3 = axes[2]
    ax3.plot(dates, df_full['z_ore'], color='#2E86AB', linewidth=1, label='锂辉石精矿 Z')
    ax3.plot(dates, df_full['z_battery'], color='#A23B72', linewidth=1, label='电池级 Z')
    ax3.plot(dates, df_full['z_industrial'], color='#F18F01', linewidth=1, label='工业级 Z')
    ax3.plot(dates, df_full['z_futures'], color='#6A994E', linewidth=1, label='期货 Z')
    ax3.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)

    # 添加均值线（在Z-Score图中，均值就是0）
    ax3.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)

    ax3.set_xlabel('日期')
    ax3.set_ylabel('Z-Score')
    ax3.set_title('四个价格Z-Score走势')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('回测结果图_全数据_四价格模型.png', dpi=200, bbox_inches='tight')
    print(f"\n📁 图表已保存: 回测结果图_全数据_四价格模型.png")
    plt.close()


# ===================== 主函数 =====================
def main():
    print("=" * 80)
    print("🔬 碳酸锂价格偏离度回测系统（四价格Z-Score模型 - 全数据版本）")
    print("=" * 80)
    print(f"\nCDI阈值: 做多 < -2.0 | 做空 > 2.0")
    print("数据模式: 全部数据既用于训练（计算均值和标准差），也用于回测")
    print("=" * 80)

    # -------------------- 读取数据 --------------------
    print("\n📂 [1/3] 读取数据...")
    try:
        dates, data_dict = read_excel_data(FILE_PATH, SHEET_NAME)
        print(f"✅ 读取成功，共 {len(dates)} 个交易日")
        print(f"   日期范围: {dates[0]} ~ {dates[-1]}")
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return

    # 创建完整DataFrame
    df_full = pd.DataFrame({
        'date': dates,
        '锂辉石精矿': data_dict['锂辉石精矿'],
        '电池级碳酸锂': data_dict['电池级碳酸锂'],
        '工业级碳酸锂': data_dict['工业级碳酸锂'],
        '主力合约结算价': data_dict['主力合约结算价'],
        '主力合约仓单': data_dict['主力合约仓单'],
        '期现基差': data_dict['期现基差']
    })

    # -------------------- 计算全数据统计 --------------------
    print("\n📊 [2/3] 计算全数据统计...")

    # 去除缺失值
    df_clean = df_full.dropna(subset=['锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约结算价'])
    stats = calculate_stats(df_clean)

    print(f"\n   全数据统计（基于 {stats['数据量']} 个交易日）:")
    print(f"   锂辉石精矿: 均值={stats['均值_锂辉石精矿']:.2f}, 标准差={stats['标准差_锂辉石精矿']:.2f}")
    print(f"   电池级碳酸锂: 均值={stats['均值_电池级碳酸锂']:.2f}, 标准差={stats['标准差_电池级碳酸锂']:.2f}")
    print(f"   工业级碳酸锂: 均值={stats['均值_工业级碳酸锂']:.2f}, 标准差={stats['标准差_工业级碳酸锂']:.2f}")
    print(f"   主力合约结算价: 均值={stats['均值_主力合约结算价']:.2f}, 标准差={stats['标准差_主力合约结算价']:.2f}")

    # -------------------- 计算全数据CDI --------------------
    print("\n🎯 [3/3] 运行回测...")

    # 计算全数据Z-Score和CDI
    df_clean = df_clean.copy()
    df_clean['z_ore'] = df_clean['锂辉石精矿'].apply(
        lambda x: calculate_zscore(x, stats['均值_锂辉石精矿'], stats['标准差_锂辉石精矿'])
    )
    df_clean['z_battery'] = df_clean['电池级碳酸锂'].apply(
        lambda x: calculate_zscore(x, stats['均值_电池级碳酸锂'], stats['标准差_电池级碳酸锂'])
    )
    df_clean['z_industrial'] = df_clean['工业级碳酸锂'].apply(
        lambda x: calculate_zscore(x, stats['均值_工业级碳酸锂'], stats['标准差_工业级碳酸锂'])
    )
    df_clean['z_futures'] = df_clean['主力合约结算价'].apply(
        lambda x: calculate_zscore(x, stats['均值_主力合约结算价'], stats['标准差_主力合约结算价'])
    )
    df_clean['cdi'] = df_clean.apply(
        lambda row: calculate_cdi(row['z_ore'], row['z_battery'], row['z_industrial'], row['z_futures']),
        axis=1
    )

    # 运行回测
    trades, df_test_with_cdi = run_backtest(df_clean, stats)

    if trades is None or len(trades) == 0:
        print("⚠️ 无交易信号产生")
        return

    # 分析结果
    results, df_trades = analyze_trades(trades)

    # 打印结果
    print_results(results, df_trades, stats)

    # 绘制图表
    plot_results(df_clean, df_trades, stats)

    print("\n" + "=" * 80)
    print("✅ 回测完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()