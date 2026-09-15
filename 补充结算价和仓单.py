# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time

warnings.filterwarnings('ignore')

# ===================== 配置参数 =====================
FILE_PATH = 'SMM_碳酸锂日度.xlsx'
SHEET_NAME = 'Sheet1'

# 主力合约映射
MAIN_CONTRACT_MAP = {
    'LC': 'LC0',  # 碳酸锂连续
}


# ===================== 读取Excel文件 =====================
def read_excel_data(file_path, sheet_name):
    """读取Excel文件，获取日期列和电池级碳酸锂价格（C列）"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    # 数据从第7行开始（索引7），因为第7行是第一个数据行（2026-07-23）
    # 第0-6行是表头信息
    data_rows = df.iloc[7:].copy()  # 修改：从索引7开始
    data_rows = data_rows.reset_index(drop=True)

    dates = []
    prices_battery = []

    for idx, row in data_rows.iterrows():
        date_val = row[0]
        price_val = row[2]

        if pd.notna(date_val) and pd.notna(price_val):
            # 统一转换为字符串格式 YYYY-MM-DD
            if isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime('%Y-%m-%d')
            elif isinstance(date_val, datetime):
                date_str = date_val.strftime('%Y-%m-%d')
            else:
                try:
                    date_str = str(date_val).strip()
                    if ' ' in date_str:
                        date_str = date_str.split(' ')[0]
                    if date_str.isdigit() and len(date_str) == 8:
                        dt = datetime.strptime(date_str, '%Y%m%d')
                        date_str = dt.strftime('%Y-%m-%d')
                except:
                    date_str = str(date_val).strip()

            dates.append(date_str)
            prices_battery.append(float(price_val))

    print(f"\n   读取到的日期: 前3个 {dates[:3]} ... 最后3个 {dates[-3:]}")
    print(f"   日期总数: {len(dates)}")

    return dates, prices_battery


# ===================== 获取主力合约结算价 =====================
def get_settlement_prices(symbol, start_date, end_date):
    """
    获取主力合约的历史结算价
    """
    result = {}

    main_contract = MAIN_CONTRACT_MAP.get(symbol.upper())
    if not main_contract:
        print(f"❌ 未找到 {symbol} 的主力合约映射")
        return result

    try:
        print(f"⏳ 正在获取 {main_contract} 的历史数据...")
        df = ak.futures_zh_daily_sina(symbol=main_contract)

        if df is None or df.empty:
            print(f"❌ 未获取到 {main_contract} 的数据")
            return result

        # 转换日期格式
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=True)

        print(f"   数据日期范围: {df['date'].min()} ~ {df['date'].max()}")
        print(f"   数据条数: {len(df)}")

        # 筛选日期范围
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df_filtered = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

        print(f"   筛选后数据条数: {len(df_filtered)}")

        # 提取结算价
        for _, row in df_filtered.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            if 'settlement' in row and pd.notna(row['settlement']) and row['settlement'] > 0:
                settlement = float(row['settlement'])
            else:
                settlement = float(row['close'])
            result[date_str] = settlement

        print(f"✅ 获取结算价成功，共 {len(result)} 条数据")

        if len(result) > 0:
            sample_keys = list(result.keys())[:5]
            print(f"   示例数据:")
            for key in sample_keys:
                print(f"     {key}: {result[key]:.0f}")

        return result

    except Exception as e:
        print(f"❌ 获取结算价失败: {e}")
        import traceback
        traceback.print_exc()
        return result


# ===================== 获取仓单数据 =====================
def get_warehouse_receipts(symbol, start_date, end_date):
    """
    使用 ak.futures_gfex_warehouse_receipt 获取广期所仓单数据
    """
    result = {}

    try:
        print(f"⏳ 正在获取 {symbol} 的仓单数据...")

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='B')

        print(f"   日期范围: {start_dt.strftime('%Y-%m-%d')} ~ {end_dt.strftime('%Y-%m-%d')}")
        print(f"   预计获取 {len(date_range)} 个交易日的数据...")

        success_count = 0
        fail_count = 0

        for i, dt in enumerate(date_range):
            date_str = dt.strftime('%Y%m%d')

            try:
                df = ak.futures_gfex_warehouse_receipt(date=date_str)

                if df is not None and isinstance(df, dict):
                    # 检查是否有碳酸锂（LC）的数据
                    if symbol in df:
                        symbol_df = df[symbol]
                        if isinstance(symbol_df, pd.DataFrame) and not symbol_df.empty:
                            total = calculate_total_receipt(symbol_df)
                            if total >= 0:  # 仓单可以为0
                                date_key = dt.strftime('%Y-%m-%d')
                                result[date_key] = total
                                success_count += 1
                    else:
                        # 有些日期可能没有该品种的仓单
                        pass

            except Exception as e:
                fail_count += 1
                if fail_count <= 3:
                    print(f"   ⚠️ {date_str} 获取失败: {str(e)[:60]}")

            # 显示进度
            if (i + 1) % 100 == 0:
                print(f"   已处理 {i + 1}/{len(date_range)} 个交易日，成功 {success_count} 条")

            time.sleep(0.15)

        print(f"✅ 仓单数据获取完成")
        print(f"   成功: {success_count} 条，失败: {fail_count} 条")

        if len(result) > 0:
            sample_keys = list(result.keys())[:5]
            print(f"   示例数据:")
            for key in sample_keys:
                print(f"     {key}: {result[key]:.0f}")

        return result

    except Exception as e:
        print(f"❌ 获取仓单数据失败: {e}")
        import traceback
        traceback.print_exc()
        return result


def calculate_total_receipt(df):
    """
    从DataFrame中计算该品种的总仓单量
    """
    if df is None or df.empty:
        return 0

    # 查找仓单量列
    receipt_col = None
    for col in df.columns:
        if '今日仓单量' in col:
            receipt_col = col
            break

    if receipt_col is None:
        for col in df.columns:
            if '仓单量' in col or '仓单' in col:
                receipt_col = col
                break

    if receipt_col:
        try:
            total = df[receipt_col].astype(float).sum()
            return total
        except:
            return 0

    return 0


# ===================== 主函数 =====================
def main():
    print("=" * 80)
    print("碳酸锂日度数据补充工具")
    print("功能：填充主力合约结算价、仓单数据，并计算基差")
    print("=" * 80)

    # 1. 读取Excel文件获取日期列表
    print("\n📂 正在读取Excel文件...")
    try:
        dates, prices_battery = read_excel_data(FILE_PATH, SHEET_NAME)

        if len(dates) == 0:
            print("❌ 未读取到任何日期数据")
            return

        print(f"✅ 读取成功，共 {len(dates)} 个交易日")
        print(f"   最新日期: {dates[0]}")
        print(f"   最旧日期: {dates[-1]}")
        print(f"   电池级碳酸锂价格范围: {min(prices_battery):.0f} ~ {max(prices_battery):.0f}")

    except Exception as e:
        print(f"❌ 读取Excel文件失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 设置数据时间范围
    start_date = dates[-1]  # 最旧的日期
    end_date = dates[0]  # 最新的日期

    print(f"\n   数据时间范围: {start_date} ~ {end_date}")

    # 2. 获取结算价数据
    print("\n📊 正在获取主力合约结算价...")
    settlement_prices = get_settlement_prices('LC', start_date, end_date)

    # 3. 获取仓单数据
    print("\n📊 正在获取仓单数据（广期所API）...")
    receipt_data = get_warehouse_receipts('LC', start_date, end_date)

    # 4. 对齐数据
    print("\n📝 正在对齐数据...")

    settlement_list = []
    receipt_list = []
    basis_list = []

    matched_count = 0
    settlement_missing = 0
    receipt_missing = 0

    for i, date_str in enumerate(dates):
        # 结算价
        if date_str in settlement_prices:
            settlement = settlement_prices[date_str]
            settlement_list.append(settlement)
            matched_count += 1
        else:
            settlement_list.append(np.nan)
            settlement_missing += 1

        # 仓单
        if date_str in receipt_data:
            receipt = receipt_data[date_str]
            receipt_list.append(receipt)
        else:
            receipt_list.append(np.nan)
            receipt_missing += 1

        # 基差
        if pd.notna(prices_battery[i]) and pd.notna(settlement_list[-1]):
            basis = prices_battery[i] - settlement_list[-1]
        else:
            basis = np.nan
        basis_list.append(basis)

    print(f"✅ 数据对齐完成")
    print(f"   结算价匹配: {matched_count}/{len(dates)} 条")
    if settlement_missing > 0:
        print(f"   ⚠️ 结算价缺失: {settlement_missing} 条")
    if receipt_missing > 0:
        print(f"   ⚠️ 仓单缺失: {receipt_missing} 条")

    # 5. 写入Excel
    print("\n💾 正在写入Excel文件...")

    try:
        df_excel = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, dtype=str)

        data_start_idx = 7  # 修改：从索引7开始（第7行是第一个数据行）

        for i, (settlement, receipt, basis) in enumerate(zip(settlement_list, receipt_list, basis_list)):
            row_idx = data_start_idx + i
            if row_idx < len(df_excel):
                if pd.notna(settlement) and not np.isnan(settlement) and settlement > 0:
                    df_excel.iloc[row_idx, 4] = str(int(settlement))
                else:
                    df_excel.iloc[row_idx, 4] = ''

                if pd.notna(receipt) and not np.isnan(receipt):
                    df_excel.iloc[row_idx, 5] = str(int(receipt))
                else:
                    df_excel.iloc[row_idx, 5] = ''

                if pd.notna(basis) and not np.isnan(basis):
                    df_excel.iloc[row_idx, 6] = str(int(basis))
                else:
                    df_excel.iloc[row_idx, 6] = ''

        with pd.ExcelWriter(FILE_PATH, engine='openpyxl', mode='w') as writer:
            df_excel.to_excel(writer, sheet_name=SHEET_NAME, index=False, header=False)

        print(f"✅ 数据已保存到 {FILE_PATH}")

        # 验证
        verify_df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None)
        print(f"\n📋 验证写入结果（前5行最新数据）:")
        print("-" * 80)
        print(f"  {'日期':<14} {'E列-结算价':<12} {'F列-仓单':<12} {'G列-基差':<12}")
        print("-" * 80)
        for i in range(7, min(12, len(verify_df))):
            date_val = verify_df.iloc[i, 0]
            date_str = date_val.strftime('%Y-%m-%d') if isinstance(date_val, pd.Timestamp) else str(date_val)
            e_val = verify_df.iloc[i, 4] if pd.notna(verify_df.iloc[i, 4]) else ''
            f_val = verify_df.iloc[i, 5] if pd.notna(verify_df.iloc[i, 5]) else ''
            g_val = verify_df.iloc[i, 6] if pd.notna(verify_df.iloc[i, 6]) else ''
            print(f"  {date_str:<14} {str(e_val):<12} {str(f_val):<12} {str(g_val):<12}")
        print("-" * 80)

        # 验证最后5行
        print(f"\n📋 验证写入结果（最后5行最旧数据）:")
        print("-" * 80)
        print(f"  {'日期':<14} {'E列-结算价':<12} {'F列-仓单':<12} {'G列-基差':<12}")
        print("-" * 80)
        for i in range(len(verify_df) - 5, len(verify_df)):
            if i >= 7:
                date_val = verify_df.iloc[i, 0]
                date_str = date_val.strftime('%Y-%m-%d') if isinstance(date_val, pd.Timestamp) else str(date_val)
                e_val = verify_df.iloc[i, 4] if pd.notna(verify_df.iloc[i, 4]) else ''
                f_val = verify_df.iloc[i, 5] if pd.notna(verify_df.iloc[i, 5]) else ''
                g_val = verify_df.iloc[i, 6] if pd.notna(verify_df.iloc[i, 6]) else ''
                print(f"  {date_str:<14} {str(e_val):<12} {str(f_val):<12} {str(g_val):<12}")
        print("-" * 80)

    except Exception as e:
        print(f"❌ 写入Excel文件失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 6. 统计
    print("\n" + "=" * 80)
    print("📊 数据统计")
    print("=" * 80)

    valid_settlements = [s for s in settlement_list if pd.notna(s) and s > 0]
    if valid_settlements:
        print(f"\n【主力合约结算价】")
        print(f"  有效数据: {len(valid_settlements)} 条")
        print(f"  最新结算价: {valid_settlements[0]:.0f} 元/吨")
        print(f"  最大值: {max(valid_settlements):.0f} 元/吨")
        print(f"  平均值: {np.mean(valid_settlements):.0f} 元/吨")

    valid_receipts = [r for r in receipt_list if pd.notna(r)]
    if valid_receipts:
        print(f"\n【仓单数据】")
        print(f"  有效数据: {len(valid_receipts)} 条")
        print(f"  最新仓单: {valid_receipts[0]:.0f} 单")
        print(f"  最大值: {max(valid_receipts):.0f} 单")
        print(f"  平均值: {np.mean(valid_receipts):.0f} 单")

    valid_basis = [b for b in basis_list if pd.notna(b)]
    if valid_basis:
        print(f"\n【基差】")
        print(f"  有效数据: {len(valid_basis)} 条")
        print(f"  最新基差: {valid_basis[0]:.0f} 元/吨")
        print(f"  平均值: {np.mean(valid_basis):.0f} 元/吨")

    print("\n" + "=" * 80)
    print("✅ 完成!")


if __name__ == '__main__':
    main()