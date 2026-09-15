# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timedelta
import warnings
import os

warnings.filterwarnings('ignore')

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC', 'Heiti SC']
matplotlib.rcParams['axes.unicode_minus'] = False

# ===================== 配置参数 =====================
FILE_PATH = 'SMM_碳酸锂日度.xlsx'
SHEET_NAME = 'Sheet1'
OUTPUT_DIR = 'charts'

# 指标配置
INDICATORS = {
    '锂辉石精矿': {'col': 'B', 'unit': '美元/吨', 'color': '#2E86AB'},
    '电池级碳酸锂': {'col': 'C', 'unit': '元/吨', 'color': '#A23B72'},
    '工业级碳酸锂': {'col': 'D', 'unit': '元/吨', 'color': '#F18F01'},
    '主力合约结算价': {'col': 'E', 'unit': '元/吨', 'color': '#C73E1D'},
    '主力合约仓单': {'col': 'F', 'unit': '单', 'color': '#6A994E'},
    '期现基差': {'col': 'G', 'unit': '元/吨', 'color': '#BC4B51'}
}


# ===================== 读取数据 =====================
def read_data(file_path, sheet_name):
    """读取Excel数据"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    # 数据从第7行开始（索引7是2026-07-23）
    data_start = 7

    # 提取数据
    dates = []
    data_dict = {name: [] for name in INDICATORS.keys()}

    for idx in range(data_start, len(df)):
        row = df.iloc[idx]
        date_val = row[0]

        if pd.isna(date_val):
            break

        # 格式化日期
        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime('%Y-%m-%d')
        elif isinstance(date_val, datetime):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val).strip()
            if ' ' in date_str:
                date_str = date_str.split(' ')[0]

        dates.append(date_str)

        # 提取各指标数据
        for name, config in INDICATORS.items():
            col_idx = ord(config['col']) - ord('A')
            val = row[col_idx]
            if pd.notna(val) and val != '':
                try:
                    data_dict[name].append(float(val))
                except:
                    data_dict[name].append(np.nan)
            else:
                data_dict[name].append(np.nan)

    return dates, data_dict


# ===================== 支撑位和阻力位计算（移植自期货代码） =====================
def get_local_low_points(data_series, window=2):
    """
    找到所有局部低点（支撑位）
    条件：当前点比左右window个点都低
    """
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
    """
    找到所有局部高点（阻力位）
    条件：当前点比左右window个点都高
    """
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
    """
    计算加权支撑位和阻力位
    使用所有局部极值点的平均值作为支撑/阻力
    如果没有找到，返回 None
    """
    local_lows = get_local_low_points(data_series, window)
    local_highs = get_local_high_points(data_series, window)

    # 支撑位：所有局部低点的平均值
    if local_lows:
        core_support = np.mean(local_lows)
    else:
        core_support = None

    # 阻力位：所有局部高点的平均值
    if local_highs:
        core_resist = np.mean(local_highs)
    else:
        core_resist = None

    return core_support, core_resist, len(local_lows), len(local_highs)


# ===================== 计算统计指标 =====================
def calculate_stats(data, dates):
    """计算各项统计指标"""
    results = {}

    # 转换为Series（日期从新到旧，与Excel一致）
    series = pd.Series(data, index=dates)
    valid_data = series.dropna()

    if len(valid_data) < 2:
        return None

    # 当前值（最新日期，即第一个）
    current_price = valid_data.iloc[0]
    current_date = valid_data.index[0]

    # 近一周（5个交易日）
    week_data = valid_data.iloc[:5] if len(valid_data) >= 5 else valid_data
    week_return = (week_data.iloc[0] - week_data.iloc[-1]) / week_data.iloc[-1] * 100 if len(week_data) > 1 else 0
    week_avg = week_data.mean()

    # 近一月（22个交易日）
    month_data = valid_data.iloc[:22] if len(valid_data) >= 22 else valid_data
    month_return = (month_data.iloc[0] - month_data.iloc[-1]) / month_data.iloc[-1] * 100 if len(month_data) > 1 else 0
    month_avg = month_data.mean()

    # 近一年（252个交易日）
    year_data = valid_data.iloc[:252] if len(valid_data) >= 252 else valid_data
    year_return = (year_data.iloc[0] - year_data.iloc[-1]) / year_data.iloc[-1] * 100 if len(year_data) > 1 else 0
    year_avg = year_data.mean()

    # ===================== 波动率计算（修复版） =====================
    def calc_volatility(data_series):
        """
        计算年化波动率
        窗口：5天/22天/252天对应一周/一月/一年
        年化：乘以 sqrt(252)
        如果数据中有0值，将0替换为1避免 log(0) 导致 -inf
        """
        if len(data_series) < 2:
            return 0

        # 数据是从新到旧，反转后计算
        reversed_data = data_series.iloc[::-1].copy()

        # 将0替换为1，避免 log(0) 出现 -inf
        # 同时将负值中的0替换（基差可能为0）
        reversed_data = reversed_data.replace(0, 1)

        # 计算对数收益率
        log_returns = np.log(reversed_data / reversed_data.shift(1))

        # 过滤 nan、inf、-inf
        log_returns = log_returns.replace([np.inf, -np.inf], np.nan).dropna()

        if len(log_returns) < 2:
            return 0

        # 年化：乘以 sqrt(252)
        return np.std(log_returns) * np.sqrt(252) * 100

    # 一周波动率：使用 week_data（5个交易日）
    week_vol = calc_volatility(week_data) if len(week_data) >= 5 else 0

    # 一月波动率：使用 month_data（22个交易日）
    month_vol = calc_volatility(month_data) if len(month_data) >= 22 else 0

    # 一年波动率：使用 year_data（252个交易日），而不是全部数据
    year_vol = calc_volatility(year_data) if len(year_data) >= 252 else 0

    # ===================== 支撑位和阻力位计算（使用移植的公式） =====================
    # 近一月支撑位/阻力位
    month_support, month_resist, month_low_count, month_high_count = calculate_weighted_support_resistance(month_data,
                                                                                                           window=2)

    # 近一年支撑位/阻力位
    year_support, year_resist, year_low_count, year_high_count = calculate_weighted_support_resistance(valid_data,
                                                                                                       window=3)

    results = {
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

    return results


# ===================== 绘图函数 =====================
def plot_indicator(dates, data, name, config):
    """绘制单个指标的图表"""
    fig, ax1 = plt.subplots(figsize=(14, 8))

    # 转换为Series（日期从新到旧）
    series = pd.Series(data, index=dates)
    valid_data = series.dropna()

    if len(valid_data) < 2:
        plt.close()
        return

    # 反转数据用于绘图（从旧到新，便于阅读）
    plot_series = valid_data.iloc[::-1]
    plot_dates = plot_series.index

    # 主图：价格曲线
    ax1.plot(plot_dates, plot_series.values, color=config['color'],
             linewidth=1.5, label=name)
    ax1.set_xlabel('日期', fontsize=12)
    ax1.set_ylabel(f'{name} ({config["unit"]})', fontsize=12, color=config['color'])
    ax1.tick_params(axis='y', labelcolor=config['color'])
    ax1.grid(True, alpha=0.3)

    # 设置x轴刻度
    step = max(1, len(plot_dates) // 60)
    xticks = plot_dates[::step]
    ax1.set_xticks(xticks)
    ax1.set_xticklabels(xticks, rotation=45, ha='right', fontsize=8)

    # 右轴：分位数（基于所有历史数据计算）
    ax2 = ax1.twinx()

    # 计算所有数据的分位数（用原始有效数据）
    sorted_data = np.sort(valid_data.values)

    # 为每个数据点计算分位数
    percentiles = []
    for val in valid_data.values:
        pct = np.searchsorted(sorted_data, val) / len(sorted_data) * 100
        percentiles.append(pct)

    # 反转分位数以匹配绘图顺序
    plot_percentiles = percentiles[::-1]

    ax2.plot(plot_dates, plot_percentiles, color='#FF6B6B',
             linewidth=1.0, linestyle='--', alpha=0.7, label='分位数(%)')
    ax2.set_ylabel('分位数 (%)', fontsize=12, color='#FF6B6B')
    ax2.tick_params(axis='y', labelcolor='#FF6B6B')
    ax2.set_ylim(0, 100)

    # 添加分位数参考线
    ax2.axhline(y=25, color='#FF6B6B', linestyle=':', alpha=0.3, linewidth=0.8)
    ax2.axhline(y=50, color='#FF6B6B', linestyle=':', alpha=0.3, linewidth=0.8)
    ax2.axhline(y=75, color='#FF6B6B', linestyle=':', alpha=0.3, linewidth=0.8)

    # 标记最新的数据点（最新日期在最后）
    if len(plot_series) > 0:
        last_date = plot_series.index[-1]
        last_price = plot_series.values[-1]
        last_pct = plot_percentiles[-1] if len(plot_percentiles) > 0 else 50

        ax1.scatter(last_date, last_price, color=config['color'], s=100,
                    zorder=5, marker='o', edgecolor='white', linewidth=2)
        ax1.annotate(f'{last_price:.0f}',
                     xy=(last_date, last_price),
                     xytext=(10, 10), textcoords='offset points',
                     fontsize=10, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

        ax2.scatter(last_date, last_pct, color='#FF6B6B', s=80,
                    zorder=5, marker='s', edgecolor='white', linewidth=2)
        ax2.annotate(f'{last_pct:.1f}%',
                     xy=(last_date, last_pct),
                     xytext=(10, -15), textcoords='offset points',
                     fontsize=10, fontweight='bold', color='#FF6B6B',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

    # 添加标题
    plt.title(f'{name} 价格走势与分位数图\n'
              f'数据范围: {plot_dates[0]} ~ {plot_dates[-1]}  |  当前值: {plot_series.values[-1]:.0f} {config["unit"]}',
              fontsize=14, fontweight='bold')

    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)

    # 添加分位数说明
    ax1.text(0.02, 0.02, '分位数说明: 当前值在所有历史数据中的分位位置 (虚线为25%/50%/75%分位线)',
             transform=ax1.transAxes, fontsize=9,
             bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    plt.tight_layout()

    # 保存图片
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    filename = f'{OUTPUT_DIR}/{name}.png'
    plt.savefig(filename, dpi=200, bbox_inches='tight')
    print(f'  图片已保存: {filename}')
    plt.close()


# ===================== 打印统计结果并保存表格 =====================
def print_stats(name, stats, config):
    """打印统计结果"""
    if stats is None:
        print(f'\n❌ {name} 数据不足，无法计算统计指标')
        return

    print('\n' + '=' * 80)
    print(f'📊 {name} 统计分析')
    print(f'   单位: {config["unit"]}')
    print('=' * 80)

    print(f'\n📅 最新数据日期: {stats["current_date"]}')
    print(f'   【当前价格】: {stats["current_price"]:.2f} {config["unit"]}')
    print(f'   数据量: {stats["data_count"]} 条')
    print(f'   历史最低: {stats["min_val"]:.2f} {config["unit"]}')
    print(f'   历史最高: {stats["max_val"]:.2f} {config["unit"]}')

    print(f'\n📈 涨跌幅:')
    print(f'   近一周: {stats["week_return"]:+.2f}%')
    print(f'   近一月: {stats["month_return"]:+.2f}%')
    print(f'   近一年: {stats["year_return"]:+.2f}%')

    print(f'\n📊 波动率 (年化收益率):')
    print(f'   近一周: {stats["week_volatility"]:.2f}%')
    print(f'   近一月: {stats["month_volatility"]:.2f}%')
    print(f'   近一年: {stats["year_volatility"]:.2f}%')

    print(f'\n📐 平均值:')
    print(f'   近一周平均值: {stats["week_avg"]:.2f} {config["unit"]}')
    print(f'   近一月平均值: {stats["month_avg"]:.2f} {config["unit"]}')
    print(f'   近一年平均值: {stats["year_avg"]:.2f} {config["unit"]}')

    print(f'\n🎯 支撑位与阻力位:')
    # 近一月
    if stats["month_support"] is not None:
        print(
            f'   近一月支撑位(平均): {stats["month_support"]:.2f} {config["unit"]} (基于{stats["month_low_count"]}个局部低点)')
    else:
        print(f'   近一月支撑位: 未找到有效支撑位')

    if stats["month_resistance"] is not None:
        print(
            f'   近一月阻力位(平均): {stats["month_resistance"]:.2f} {config["unit"]} (基于{stats["month_high_count"]}个局部高点)')
    else:
        print(f'   近一月阻力位: 未找到有效阻力位')

    # 近一年
    if stats["year_support"] is not None:
        print(
            f'   近一年支撑位(平均): {stats["year_support"]:.2f} {config["unit"]} (基于{stats["year_low_count"]}个局部低点)')
    else:
        print(f'   近一年支撑位: 未找到有效支撑位')

    if stats["year_resistance"] is not None:
        print(
            f'   近一年阻力位(平均): {stats["year_resistance"]:.2f} {config["unit"]} (基于{stats["year_high_count"]}个局部高点)')
    else:
        print(f'   近一年阻力位: 未找到有效阻力位')

    # 当前位置判断
    if stats["current_price"] > stats["year_avg"]:
        print(
            f'\n💡 当前价格高于近一年均值 {((stats["current_price"] - stats["year_avg"]) / stats["year_avg"] * 100):+.2f}%，处于偏强位置')
    else:
        print(
            f'\n💡 当前价格低于近一年均值 {((stats["year_avg"] - stats["current_price"]) / stats["year_avg"] * 100):+.2f}%，处于偏弱位置')


def save_stats_table(all_stats):
    """保存统计结果到Excel表格"""
    if not all_stats:
        print('\n⚠️ 无统计数据可保存')
        return

    # 构建表格数据
    table_data = []

    for name, stats in all_stats.items():
        row = {
            '指标': name,
            '单位': INDICATORS[name]['unit'],
            '最新日期': stats['current_date'],
            '当前值': stats['current_price'],
            '数据量': stats['data_count'],
            '历史最低': stats['min_val'],
            '历史最高': stats['max_val'],
            '近一周涨跌幅(%)': stats['week_return'],
            '近一月涨跌幅(%)': stats['month_return'],
            '近一年涨跌幅(%)': stats['year_return'],
            '近一周波动率(%)': stats['week_volatility'],
            '近一月波动率(%)': stats['month_volatility'],
            '近一年波动率(%)': stats['year_volatility'],
            '近一周均值': stats['week_avg'],
            '近一月均值': stats['month_avg'],
            '近一年均值': stats['year_avg'],
            '近一月支撑位': stats['month_support'] if stats['month_support'] is not None else '未找到有效支撑位',
            '近一月阻力位': stats['month_resistance'] if stats['month_resistance'] is not None else '未找到有效阻力位',
            '近一年支撑位': stats['year_support'] if stats['year_support'] is not None else '未找到有效支撑位',
            '近一年阻力位': stats['year_resistance'] if stats['year_resistance'] is not None else '未找到阻力位',
        }
        table_data.append(row)

    # 转换为DataFrame
    df = pd.DataFrame(table_data)

    # 格式化数值列
    numeric_cols = ['当前值', '历史最低', '历史最高', '近一周均值', '近一月均值', '近一年均值']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else '')

    pct_cols = ['近一周涨跌幅(%)', '近一月涨跌幅(%)', '近一年涨跌幅(%)',
                '近一周波动率(%)', '近一月波动率(%)', '近一年波动率(%)']
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f'{x:+.2f}%' if pd.notna(x) else '')

    # 保存到Excel
    output_file = '统计结果汇总表.xlsx'
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='统计汇总', index=False)

        print(f'\n📁 统计表格已保存: {os.path.abspath(output_file)}')
    except Exception as e:
        print(f'\n❌ 保存表格失败: {e}')
        # 尝试保存为CSV
        try:
            csv_file = '统计结果汇总表.csv'
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f'📁 已保存为CSV格式: {os.path.abspath(csv_file)}')
        except:
            print('❌ 保存CSV也失败，请检查权限')


# ===================== 主函数 =====================
def main():
    print('=' * 80)
    print('碳酸锂日度数据分析工具')
    print('功能：六指标时间序列图（含分位数）+ 统计指标计算')
    print('=' * 80)

    # 1. 读取数据
    print('\n📂 正在读取数据...')
    try:
        dates, data_dict = read_data(FILE_PATH, SHEET_NAME)
        print(f'✅ 读取成功，共 {len(dates)} 个交易日')
        print(f'   日期范围: {dates[0]} ~ {dates[-1]}')
    except Exception as e:
        print(f'❌ 读取失败: {e}')
        return

    # 2. 创建输出目录
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f'\n📁 创建输出目录: {OUTPUT_DIR}')

    # 3. 处理每个指标
    all_stats = {}

    for name, config in INDICATORS.items():
        print(f'\n🔍 正在处理: {name}...')

        data = data_dict[name]
        valid_count = sum(1 for x in data if pd.notna(x))
        print(f'   有效数据: {valid_count} 条')

        if valid_count < 5:
            print(f'   ⚠️ 数据不足，跳过')
            continue

        # 计算统计指标
        stats = calculate_stats(data, dates)
        if stats:
            all_stats[name] = stats

            # 打印统计结果
            print_stats(name, stats, config)

        # 绘图
        plot_indicator(dates, data, name, config)

    # 4. 汇总表格
    print('\n' + '=' * 80)
    print('📋 各指标当前数据汇总')
    print('=' * 80)
    print(f"{'指标':<12} {'当前值':<12} {'近一周涨跌':<10} {'近一月涨跌':<10} {'近一年涨跌':<10} {'近一月波动率':<10}")
    print('-' * 80)

    for name, stats in all_stats.items():
        print(f"{name:<12} {stats['current_price']:<12,.0f} {stats['week_return']:>+8.2f}% "
              f"{stats['month_return']:>+8.2f}% {stats['year_return']:>+8.2f}% "
              f"{stats['month_volatility']:>8.2f}%")

    # 5. 保存统计表格
    if all_stats:
        save_stats_table(all_stats)

    print('\n' + '=' * 80)
    print('✅ 分析完成！')
    print(f'📁 图片已保存至: {os.path.abspath(OUTPUT_DIR)}')
    print('=' * 80)


if __name__ == '__main__':
    main()