# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import warnings
import calendar

warnings.filterwarnings('ignore')

# ===================== 品种映射表 =====================
GFEX_SYMBOL_MAP = {
    'LC': '碳酸锂',
    'SI': '工业硅',
    'PS': '多晶硅',
    'PD': '钯',
    'PT': '铂',
}


def get_trading_days(year, month):
    """
    获取指定月份的所有交易日
    """
    try:
        trade_cal = ak.tool_trade_date_hist_sina()
        trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date'])

        start_dt = datetime(year, month, 1)
        if month == 12:
            end_dt = datetime(year + 1, 1, 1)
        else:
            end_dt = datetime(year, month + 1, 1)

        trading_days = trade_cal[(trade_cal['trade_date'] >= start_dt) &
                                 (trade_cal['trade_date'] < end_dt)]

        trading_days = trading_days['trade_date'].tolist()
        trading_days.sort()

        return trading_days

    except Exception as e:
        print(f"⚠️  获取交易日历失败: {e}")
        trading_days = []
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        current = start_date
        while current < end_date:
            if current.weekday() < 5:
                trading_days.append(current)
            current += timedelta(days=1)

        return trading_days


def get_warehouse_data(date_str, symbol='LC'):
    """
    获取指定日期发布的仓单数据
    注意：该日期发布的数据是前一个交易日收盘后的仓单情况
    """
    try:
        result = ak.futures_gfex_warehouse_receipt(date=date_str)

        if result is None:
            return None, None

        if isinstance(result, pd.DataFrame):
            if result.empty:
                return None, None
            return result, date_str

        elif isinstance(result, dict):
            if symbol in result:
                df = result[symbol]
                if not df.empty:
                    return df, date_str
            return None, None

        return None, None

    except Exception as e:
        return None, None


def get_symbol_total_receipt(df):
    """
    从DataFrame中计算该品种的总仓单量
    """
    if df is None or df.empty:
        return 0

    receipt_col = None
    for col in df.columns:
        if '今日仓单量' in col or '仓单量' in col:
            receipt_col = col
            break

    if receipt_col is None:
        for col in df.columns:
            if '仓单' in col:
                receipt_col = col
                break

    if receipt_col:
        try:
            total = df[receipt_col].astype(float).sum()
            return total
        except:
            return 0

    return 0


def get_previous_trading_day(trading_days, current_date):
    """
    获取当前交易日的前一个交易日
    """
    try:
        idx = trading_days.index(current_date)
        if idx > 0:
            return trading_days[idx - 1]
        else:
            return None
    except:
        return None


def get_symbol_warehouse_summary(symbol, year, month):
    """
    获取指定品种在指定月份的仓单汇总
    正确处理数据日期与实际仓单日期的关系
    """
    print("\n" + "=" * 80)
    print(f"📊 广期所 {symbol}({GFEX_SYMBOL_MAP.get(symbol, '')}) 仓单数据：{year}年{month}月")
    print("=" * 80)
    print("📌 说明：数据显示的是每个交易日收盘后的仓单情况")

    # 获取交易日
    trading_days = get_trading_days(year, month)

    if not trading_days:
        print("❌ 获取交易日失败")
        return None

    print(f"\n📅 该月共有 {len(trading_days)} 个交易日")

    # 获取该月所有交易日的仓单数据
    all_data = []
    missing_days = []

    print(f"\n⏳ 正在获取 {year}年{month}月 的仓单数据...")

    for i, dt in enumerate(trading_days, 1):
        date_str = dt.strftime('%Y%m%d')

        df, actual_date = get_warehouse_data(date_str, symbol)

        if df is not None:
            total = get_symbol_total_receipt(df)

            # 确定这个数据代表的是哪一天的仓单
            # 数据发布日期是 dt，代表的是 dt-1 交易日收盘后的仓单
            previous_day = get_previous_trading_day(trading_days, dt)

            if previous_day:
                # 如果前一个交易日存在，数据代表前一个交易日的收盘仓单
                data_date = previous_day
                data_date_str = previous_day.strftime('%Y-%m-%d')
            else:
                # 如果是当月第一个交易日，数据代表上个月最后一个交易日的仓单
                data_date = dt
                data_date_str = f"{dt.strftime('%Y-%m-%d')} (月初数据)"

            all_data.append({
                'publish_date': dt,  # 数据发布日期
                'publish_date_str': date_str,
                'data_date': data_date,  # 数据代表的实际仓单日期
                'data_date_str': data_date_str,
                'total_receipt': total,
                'detail': df
            })

            if i % 5 == 0:
                print(f"  [{i}/{len(trading_days)}] 发布:{date_str} -> 仓单日期:{data_date_str} 仓单:{total:>8,.0f} 手")
        else:
            missing_days.append(date_str)

    if not all_data:
        print(f"❌ 未获取到 {symbol} 的仓单数据")
        return None

    if missing_days:
        print(f"⚠️  有 {len(missing_days)} 个交易日无数据: {', '.join(missing_days[:5])}...")

    print(f"✅ 成功获取 {len(all_data)} 个交易日的仓单数据")

    return all_data


def compare_monthly_receipt(symbol, year, month):
    """
    对比指定月份第一个和最后一个交易日的仓单增减
    """
    # 获取该月所有仓单数据
    all_data = get_symbol_warehouse_summary(symbol, year, month)

    if not all_data or len(all_data) < 2:
        print("❌ 数据不足，无法对比（至少需要2个交易日的数据）")
        return None

    # 第一个交易日的数据
    first_day = all_data[0]
    # 最后一个交易日的数据
    last_day = all_data[-1]

    # 输出详细结果
    print("\n" + "=" * 80)
    print(f"📊 {symbol}({GFEX_SYMBOL_MAP.get(symbol, '')}) 仓单月度对比：{year}年{month}月")
    print("=" * 80)

    print(
        f"\n📅 第一个交易日: {first_day['data_date'].strftime('%Y-%m-%d')} (数据发布于 {first_day['publish_date'].strftime('%Y-%m-%d')})")
    print(f"   总仓单量: {first_day['total_receipt']:>12,.0f} 手")

    print(
        f"\n📅 最后一个交易日: {last_day['data_date'].strftime('%Y-%m-%d')} (数据发布于 {last_day['publish_date'].strftime('%Y-%m-%d')})")
    print(f"   总仓单量: {last_day['total_receipt']:>12,.0f} 手")

    # 计算增减量
    change = last_day['total_receipt'] - first_day['total_receipt']
    change_pct = (change / first_day['total_receipt'] * 100) if first_day['total_receipt'] > 0 else 0

    print("\n" + "-" * 80)
    print("📈 月度仓单变化明细 (按实际仓单日期):")
    print("-" * 80)
    print(f"{'仓单日期':<15} {'发布日期':<12} {'仓单量':>12} {'日增减':>12}")
    print("-" * 80)

    prev_receipt = None
    for data in all_data:
        if prev_receipt is not None:
            daily_change = data['total_receipt'] - prev_receipt
            change_str = f"{daily_change:>+12,.0f}"
        else:
            change_str = f"{'—':>12}"

        print(f"{data['data_date'].strftime('%Y-%m-%d'):<15} "
              f"{data['publish_date'].strftime('%m-%d'):<12} "
              f"{data['total_receipt']:>12,.0f} "
              f"{change_str}")
        prev_receipt = data['total_receipt']

    # 最终结果
    print("\n" + "=" * 80)
    print("✅ 【最终结果】仓单增减量")
    print("=" * 80)

    print(f"\n🎯 计算方式: 月末仓单 - 月初仓单")
    print(f"   {last_day['data_date'].strftime('%Y-%m-%d')} - {first_day['data_date'].strftime('%Y-%m-%d')}")
    print(f"   = {last_day['total_receipt']:,.0f} - {first_day['total_receipt']:,.0f}")
    print(f"   = {change:,.0f} 手")

    if change > 0:
        print(f"\n   📈 结论: {month}月仓单增加 {change:,.0f} 手 (增幅: {change_pct:.2f}%)")
        print(f"   💡 解读: 市场交割意愿增强，可供交割货源增加")
    elif change < 0:
        print(f"\n   📉 结论: {month}月仓单减少 {abs(change):,.0f} 手 (降幅: {abs(change_pct):.2f}%)")
        print(f"   💡 解读: 市场交割意愿减弱，仓单流出或注销增加")
    else:
        print(f"\n   ➡️ 结论: {month}月仓单量持平，无变化")

    # 详细仓单明细
    print("\n" + "-" * 80)
    show_details = input("是否显示详细仓单明细（按仓库）？(y/n): ").strip().lower()
    if show_details == 'y':
        print(f"\n📋 月初 ({first_day['data_date'].strftime('%Y-%m-%d')}) 仓单明细:")
        print("-" * 60)
        if 'detail' in first_day:
            print(first_day['detail'].to_string(index=False))

        print(f"\n📋 月末 ({last_day['data_date'].strftime('%Y-%m-%d')}) 仓单明细:")
        print("-" * 60)
        if 'detail' in last_day:
            print(last_day['detail'].to_string(index=False))

    print("\n" + "=" * 80)

    return {
        'symbol': symbol,
        'year': year,
        'month': month,
        'first_day': first_day,
        'last_day': last_day,
        'change': change,
        'change_pct': change_pct,
        'all_days': all_data
    }


def main():
    print("=" * 80)
    print("广期所注册仓单月度对比工具 (修正版)")
    print("说明：正确理解数据发布日期与实际仓单日期的关系")
    print("=" * 80)

    while True:
        print("\n请选择功能:")
        print("1. 对比单个月份的仓单增减")
        print("2. 对比两个月份的仓单增减")
        print("3. 查看多个月份的仓单变化趋势")
        print("4. 退出")

        choice = input("\n请输入选择 (1/2/3/4): ").strip()

        if choice == '4':
            print("程序退出")
            break

        elif choice == '1':
            symbol = input("\n请输入品种代码 (如 LC, SI): ").strip().upper()
            if symbol not in GFEX_SYMBOL_MAP:
                print(f"⚠️  警告: {symbol} 可能不是广期所品种")

            year = int(input("请输入年份 (如 2026): ").strip())
            month = int(input("请输入月份 (如 6): ").strip())

            compare_monthly_receipt(symbol, year, month)

        elif choice == '2':
            symbol = input("\n请输入品种代码 (如 LC, SI): ").strip().upper()
            if symbol not in GFEX_SYMBOL_MAP:
                print(f"⚠️  警告: {symbol} 可能不是广期所品种")

            year = int(input("请输入年份 (如 2026): ").strip())
            month1 = int(input("请输入第一个月份 (如 5): ").strip())
            month2 = int(input("请输入第二个月份 (如 6): ").strip())

            print(f"\n📊 对比 {symbol} {year}年{month1}月 vs {year}年{month2}月")
            print("-" * 80)

            result1 = compare_monthly_receipt(symbol, year, month1)
            result2 = compare_monthly_receipt(symbol, year, month2)

            if result1 and result2:
                print("\n" + "=" * 80)
                print(f"📊 {symbol} 仓单月度对比汇总")
                print("=" * 80)
                print(f"\n{year}年{month1}月仓单变化: {result1['change']:+,.0f} ({result1['change_pct']:+.2f}%)")
                print(f"{year}年{month2}月仓单变化: {result2['change']:+,.0f} ({result2['change_pct']:+.2f}%)")

                month1_avg = sum([d['total_receipt'] for d in result1['all_days']]) / len(result1['all_days'])
                month2_avg = sum([d['total_receipt'] for d in result2['all_days']]) / len(result2['all_days'])

                avg_change = month2_avg - month1_avg
                print(f"\n月均仓单对比:")
                print(f"  {year}年{month1}月均仓单: {month1_avg:,.0f}")
                print(f"  {year}年{month2}月均仓单: {month2_avg:,.0f}")
                print(f"  月均仓单变化: {avg_change:+,.0f}")

        elif choice == '3':
            symbol = input("\n请输入品种代码 (如 LC, SI): ").strip().upper()
            if symbol not in GFEX_SYMBOL_MAP:
                print(f"⚠️  警告: {symbol} 可能不是广期所品种")

            year = int(input("请输入年份 (如 2026): ").strip())
            months_input = input("请输入月份，用逗号分隔 (如 5,6,7,8): ").strip()
            months = [int(m.strip()) for m in months_input.split(',')]

            results = []
            for month in months:
                print(f"\n📊 处理 {year}年{month}月...")
                result = compare_monthly_receipt(symbol, year, month)
                if result:
                    results.append(result)

            if len(results) >= 2:
                print("\n" + "=" * 80)
                print(f"📊 {symbol} 各月份仓单变化趋势")
                print("=" * 80)
                print(f"{'月份':<12} {'月初仓单':>14} {'月末仓单':>14} {'月度变化':>14} {'变化率':>10}")
                print("-" * 80)

                for result in results:
                    print(f"{result['year']}年{result['month']}月{'':<4} "
                          f"{result['first_day']['total_receipt']:>14,.0f} "
                          f"{result['last_day']['total_receipt']:>14,.0f} "
                          f"{result['change']:>14,+.0f} "
                          f"{result['change_pct']:>9.2f}%")

        else:
            print("❌ 无效选择，请重新输入")


if __name__ == "__main__":
    main()