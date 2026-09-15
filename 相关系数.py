# # -*- coding: utf-8 -*-
# """
# 碳酸锂精矿-碳酸锂偏离度监控系统
# 功能：
# 1. 从Excel读取历史数据，计算三个比值的均值和标准差
# 2. 手动输入锂精矿、电池级、工业级现货价格
# 3. 自动获取碳酸锂主力合约实时价格（每分钟更新）
# 4. 计算Z-Score和CDI，输出交易信号
# """
#
# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib
# from datetime import datetime, timedelta
# import warnings
# import os
# import time
# import re
# import random
# import akshare as ak
# import json
#
# warnings.filterwarnings('ignore')
#
# # 设置中文字体
# matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC', 'Heiti SC']
# matplotlib.rcParams['axes.unicode_minus'] = False
#
# # ===================== 配置参数 =====================
# FILE_PATH = 'SMM_碳酸锂日度.xlsx'
# SHEET_NAME = 'Sheet1'
#
# # 指标列配置
# INDICATOR_COLS = {
#     '锂辉石精矿': 'B',
#     '电池级碳酸锂': 'C',
#     '工业级碳酸锂': 'D',
#     '主力合约结算价': 'E',
#     '主力合约仓单': 'F',
#     '期现基差': 'G'
# }
#
# # CDI权重配置
# WEIGHTS = {
#     '电池级': 0.25,
#     '工业级': 0.25,
#     '期货': 0.50
# }
#
# # 交易信号阈值
# SIGNAL_THRESHOLDS = {
#     'strong_bull': 2.0,  # > 2.0 强烈看多
#     'moderate_bull': 1.5,  # 1.5 ~ 2.0 轻度看多
#     'neutral_high': 1.5,  # -1.5 ~ 1.5 观望
#     'moderate_bear': -1.5,  # -2.0 ~ -1.5 轻度看空
#     'strong_bear': -2.0  # < -2.0 强烈看空
# }
#
# # 期货品种映射（碳酸锂）
# FUTURES_SYMBOL = 'LC0'  # 碳酸锂连续合约
# CONTRACT_MONTHS = ['2609', '2610', '2611', '2612', '2701', '2702', '2703', '2704', '2705', '2706', '2707', '2708']
#
#
# # ===================== 数据读取模块 =====================
# def read_excel_data(file_path, sheet_name):
#     """
#     从Excel读取六个指标的历史数据
#     返回：日期列表和六个指标的数据字典
#     """
#     df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
#
#     # 数据从第7行开始（索引7是2026-07-23）
#     data_start = 7
#
#     dates = []
#     data_dict = {name: [] for name in INDICATOR_COLS.keys()}
#
#     for idx in range(data_start, len(df)):
#         row = df.iloc[idx]
#         date_val = row[0]
#
#         if pd.isna(date_val):
#             break
#
#         # 格式化日期
#         if isinstance(date_val, pd.Timestamp):
#             date_str = date_val.strftime('%Y-%m-%d')
#         elif isinstance(date_val, datetime):
#             date_str = date_val.strftime('%Y-%m-%d')
#         else:
#             date_str = str(date_val).strip()
#             if ' ' in date_str:
#                 date_str = date_str.split(' ')[0]
#
#         dates.append(date_str)
#
#         # 提取各指标数据
#         for name, col in INDICATOR_COLS.items():
#             col_idx = ord(col) - ord('A')
#             val = row[col_idx]
#             if pd.notna(val) and val != '':
#                 try:
#                     data_dict[name].append(float(val))
#                 except:
#                     data_dict[name].append(np.nan)
#             else:
#                 data_dict[name].append(np.nan)
#
#     return dates, data_dict
#
#
# # ===================== 历史数据统计分析模块 =====================
# def calculate_historical_stats(dates, data_dict):
#     """
#     计算历史数据的比值、均值和标准差
#     返回：三个比值的均值和标准差
#     """
#     # 创建DataFrame
#     df = pd.DataFrame({
#         'date': dates,
#         '精矿': data_dict['锂辉石精矿'],
#         '电池级': data_dict['电池级碳酸锂'],
#         '工业级': data_dict['工业级碳酸锂'],
#         '期货': data_dict['主力合约结算价']
#     })
#
#     # 转换精矿价格为元/吨（美元转人民币，使用固定汇率7.2）
#     # 注意：这里使用7.2作为汇率，实际应根据需要调整
#     EXCHANGE_RATE = 1
#     df['精矿_元'] = df['精矿'] * EXCHANGE_RATE
#
#     # 计算三个比值 = 精矿价格 * 7 / 碳酸锂价格
#     # 这里的7是转换系数（约7吨精矿产1吨碳酸锂）
#     CONVERSION_FACTOR = 7
#
#     df['比值_电池级'] = (df['精矿_元'] * CONVERSION_FACTOR) / df['电池级']
#     df['比值_工业级'] = (df['精矿_元'] * CONVERSION_FACTOR) / df['工业级']
#     df['比值_期货'] = (df['精矿_元'] * CONVERSION_FACTOR) / df['期货']
#
#     # 去除无效数据
#     df_clean = df.dropna(subset=['比值_电池级', '比值_工业级', '比值_期货'])
#
#     if len(df_clean) < 10:
#         print("⚠️ 历史数据不足，请检查数据文件")
#         return None
#
#     # 计算均值和标准差
#     stats = {
#         '均值_电池级': df_clean['比值_电池级'].mean(),
#         '均值_工业级': df_clean['比值_工业级'].mean(),
#         '均值_期货': df_clean['比值_期货'].mean(),
#         '标准差_电池级': df_clean['比值_电池级'].std(),
#         '标准差_工业级': df_clean['比值_工业级'].std(),
#         '标准差_期货': df_clean['比值_期货'].std(),
#         '数据量': len(df_clean),
#         '最新日期': df_clean['date'].iloc[-1],
#         '历史比值_电池级': df_clean['比值_电池级'].tolist(),
#         '历史比值_工业级': df_clean['比值_工业级'].tolist(),
#         '历史比值_期货': df_clean['比值_期货'].tolist(),
#     }
#
#     print(f"\n📊 历史统计（基于 {stats['数据量']} 个交易日）")
#     print(f"   最新日期: {stats['最新日期']}")
#     print(f"\n   比值_电池级: 均值={stats['均值_电池级']:.4f}, 标准差={stats['标准差_电池级']:.4f}")
#     print(f"   比值_工业级: 均值={stats['均值_工业级']:.4f}, 标准差={stats['标准差_工业级']:.4f}")
#     print(f"   比值_期货:   均值={stats['均值_期货']:.4f}, 标准差={stats['标准差_期货']:.4f}")
#
#     return stats
#
#
# # ===================== 期货实时价格获取模块 =====================
# def get_futures_realtime(contract_code='LC0'):
#     """
#     获取碳酸锂主力合约实时价格
#     使用akshare获取
#     """
#     try:
#         # 获取实时行情
#         df = ak.futures_zh_realtime(symbol="碳酸锂")
#
#         if df is None or df.empty:
#             return None
#
#         # 查找主力合约（按成交量排序取第一个）
#         df_sorted = df.sort_values('volume', ascending=False)
#
#         # 查找LC开头的合约
#         lc_df = df_sorted[df_sorted['symbol'].str.startswith('LC')]
#
#         if lc_df.empty:
#             # 如果没有LC开头，尝试找碳酸锂相关
#             lc_df = df_sorted[df_sorted['name'].str.contains('碳酸锂')]
#
#         if lc_df.empty:
#             # 使用第一个
#             lc_df = df_sorted.head(1)
#
#         row = lc_df.iloc[0]
#
#         return {
#             'symbol': row.get('symbol', ''),
#             'price': float(row.get('trade', 0)),
#             'open': float(row.get('open', 0)),
#             'high': float(row.get('high', 0)),
#             'low': float(row.get('low', 0)),
#             'volume': int(row.get('volume', 0)),
#             'position': int(row.get('position', 0)),
#             'change_pct': float(row.get('changepercent', 0)),
#             'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         }
#
#     except Exception as e:
#         print(f"⚠️ 获取期货价格失败: {e}")
#
#         # 备用方案：尝试使用连续合约
#         try:
#             df = ak.futures_zh_minute_sina(symbol='LC0', period='1')
#             if df is not None and not df.empty:
#                 last_row = df.iloc[-1]
#                 return {
#                     'symbol': 'LC0',
#                     'price': float(last_row.get('close', 0)),
#                     'open': float(last_row.get('open', 0)),
#                     'high': float(last_row.get('high', 0)),
#                     'low': float(last_row.get('low', 0)),
#                     'volume': int(last_row.get('volume', 0)),
#                     'position': 0,
#                     'change_pct': 0,
#                     'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#                 }
#         except:
#             pass
#
#         return None
#
#
# # ===================== 核心计算模块 =====================
# def calculate_ratio(ore_price_usd, carbonate_price, exchange_rate=7.2, conversion_factor=7):
#     """
#     计算精矿/碳酸锂价格比
#     ratio = (精矿价格 * 汇率 * 转换系数) / 碳酸锂价格
#     """
#     ore_price_rmb = ore_price_usd * exchange_rate
#     ratio = (ore_price_rmb * conversion_factor) / carbonate_price
#     return ratio
#
#
# def calculate_zscore(current_ratio, mean, std):
#     """计算Z-Score"""
#     if std is None or std == 0:
#         return 0
#     return (current_ratio - mean) / std
#
#
# def calculate_cdi(z_battery, z_industrial, z_futures, weights=None):
#     """计算综合偏离指数CDI"""
#     if weights is None:
#         weights = WEIGHTS
#
#     cdi = (weights['电池级'] * z_battery +
#            weights['工业级'] * z_industrial +
#            weights['期货'] * z_futures)
#     return cdi
#
#
# def get_trading_signal(cdi):
#     """根据CDI值生成交易信号"""
#     if cdi > 2.0:
#         return {
#             'signal': '强烈看多',
#             'direction': 'BUY',
#             'level': 'strong',
#             'description': '整体严重低估（成本高、产品价格低），强烈看多碳酸锂',
#             'action': '多期货或现货'
#         }
#     elif cdi > 1.5:
#         return {
#             'signal': '轻度看多',
#             'direction': 'BUY',
#             'level': 'moderate',
#             'description': '轻度低估，可轻仓试多',
#             'action': '轻仓试多'
#         }
#     elif cdi >= -1.5:  # ← 关键修复：-1.5 ~ 1.5 之间为观望
#         return {
#             'signal': '观望',
#             'direction': 'NEUTRAL',
#             'level': 'neutral',
#             'description': '比值处于正常区间，观望',
#             'action': '观望'
#         }
#     elif cdi > -2.0:
#         return {
#             'signal': '轻度看空',
#             'direction': 'SELL',
#             'level': 'moderate',
#             'description': '轻度高估，可轻仓试空',
#             'action': '轻仓试空'
#         }
#     else:  # cdi <= -2.0
#         return {
#             'signal': '强烈看空',
#             'direction': 'SELL',
#             'level': 'strong',
#             'description': '整体严重高估（成本低、产品价格高），强烈看空碳酸锂',
#             'action': '空期货或套保'
#         }
#
#
# # ===================== 主程序 =====================
# def main():
#     print("=" * 80)
#     print("🔬 碳酸锂精矿-碳酸锂偏离度监控系统")
#     print("=" * 80)
#     print("\n功能说明:")
#     print("  1. 从Excel读取历史数据，计算三个比值的均值和标准差")
#     print("  2. 手动输入锂精矿、电池级、工业级现货价格")
#     print("  3. 自动获取碳酸锂主力合约实时价格（每分钟更新）")
#     print("  4. 计算Z-Score和CDI，输出交易信号")
#     print("=" * 80)
#
#     # -------------------- 第一步：读取历史数据 --------------------
#     print("\n📂 [1/4] 读取历史数据...")
#     try:
#         dates, data_dict = read_excel_data(FILE_PATH, SHEET_NAME)
#         print(f"✅ 读取成功，共 {len(dates)} 个交易日")
#         print(f"   日期范围: {dates[0]} ~ {dates[-1]}")
#     except Exception as e:
#         print(f"❌ 读取失败: {e}")
#         return
#
#     # -------------------- 第二步：计算历史统计 --------------------
#     print("\n📊 [2/4] 计算历史统计...")
#     stats = calculate_historical_stats(dates, data_dict)
#     if stats is None:
#         print("❌ 历史统计计算失败")
#         return
#
#     # 显示历史比值分布
#     print("\n📈 历史比值分布:")
#     print(f"   电池级比值: 均值={stats['均值_电池级']:.4f}, 标准差={stats['标准差_电池级']:.4f}")
#     print(f"   工业级比值: 均值={stats['均值_工业级']:.4f}, 标准差={stats['标准差_工业级']:.4f}")
#     print(f"   期货比值:   均值={stats['均值_期货']:.4f}, 标准差={stats['标准差_期货']:.4f}")
#
#     # -------------------- 第三步：手动输入现货价格 --------------------
#     print("\n💵 [3/4] 输入现货价格")
#     print("-" * 40)
#     print("注: 锂精矿价格为美元/吨，碳酸锂价格为元/吨")
#     print("-" * 40)
#
#     try:
#         ore_price = float(input("请输入锂精矿价格 (美元/吨): ").strip())
#         battery_price = float(input("请输入电池级碳酸锂价格 (元/吨): ").strip())
#         industrial_price = float(input("请输入工业级碳酸锂价格 (元/吨): ").strip())
#     except ValueError:
#         print("❌ 输入格式错误，请输入数字")
#         return
#
#     print(f"\n✅ 输入确认:")
#     print(f"   锂精矿: {ore_price:.2f} 美元/吨")
#     print(f"   电池级碳酸锂: {battery_price:.2f} 元/吨")
#     print(f"   工业级碳酸锂: {industrial_price:.2f} 元/吨")
#
#     # -------------------- 第四步：实时监控 --------------------
#     print("\n🔄 [4/4] 开始实时监控...")
#     print("=" * 80)
#     print("按 Ctrl+C 停止监控")
#     print("=" * 80)
#
#     # 计算当前比值（使用固定汇率7.2）
#     EXCHANGE_RATE = 1
#     CONVERSION_FACTOR = 7
#
#     current_ratio_battery = calculate_ratio(ore_price, battery_price, EXCHANGE_RATE, CONVERSION_FACTOR)
#     current_ratio_industrial = calculate_ratio(ore_price, industrial_price, EXCHANGE_RATE, CONVERSION_FACTOR)
#
#     print(f"\n📐 当前比值（基于输入价格）:")
#     print(f"   电池级比值: {current_ratio_battery:.4f}")
#     print(f"   工业级比值: {current_ratio_industrial:.4f}")
#
#     # 计算Z-Score（现货端）
#     z_battery = calculate_zscore(current_ratio_battery, stats['均值_电池级'], stats['标准差_电池级'])
#     z_industrial = calculate_zscore(current_ratio_industrial, stats['均值_工业级'], stats['标准差_工业级'])
#
#     print(f"\n📊 现货端Z-Score:")
#     print(f"   电池级 Z = {z_battery:+.4f}")
#     print(f"   工业级 Z = {z_industrial:+.4f}")
#
#     # 初始化历史记录用于绘图
#     history = {
#         'time': [],
#         'futures_price': [],
#         'ratio_futures': [],
#         'z_futures': [],
#         'cdi': [],
#         'signal': []
#     }
#
#     update_count = 0
#
#     try:
#         while True:
#             # 获取期货实时价格
#             futures_data = get_futures_realtime()
#
#             if futures_data is None or futures_data['price'] <= 0:
#                 print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取期货价格失败，等待重试...")
#                 time.sleep(10)
#                 continue
#
#             futures_price = futures_data['price']
#
#             # 计算期货比值
#             current_ratio_futures = calculate_ratio(ore_price, futures_price, EXCHANGE_RATE, CONVERSION_FACTOR)
#
#             # 计算期货Z-Score
#             z_futures = calculate_zscore(current_ratio_futures, stats['均值_期货'], stats['标准差_期货'])
#
#             # 计算CDI
#             cdi = calculate_cdi(z_battery, z_industrial, z_futures)
#
#             # 获取交易信号
#             signal = get_trading_signal(cdi)
#
#             # 记录历史
#             update_count += 1
#             current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#             history['time'].append(current_time)
#             history['futures_price'].append(futures_price)
#             history['ratio_futures'].append(current_ratio_futures)
#             history['z_futures'].append(z_futures)
#             history['cdi'].append(cdi)
#             history['signal'].append(signal['signal'])
#
#             # ===== 输出结果 =====
#             print("\n" + "=" * 80)
#             print(f"🕐 更新时间: {current_time}  (第{update_count}次更新)")
#             print("=" * 80)
#
#             print(f"\n📈 期货行情:")
#             print(f"   主力合约: {futures_data.get('symbol', 'N/A')}")
#             print(f"   最新价: {futures_price:.2f} 元/吨")
#             print(f"   涨跌幅: {futures_data.get('change_pct', 0):+.2f}%")
#             print(f"   成交量: {futures_data.get('volume', 0):,}")
#
#             print(f"\n📐 比值分析:")
#             print(f"   电池级比值: {current_ratio_battery:.4f}  (历史均值: {stats['均值_电池级']:.4f})")
#             print(f"   工业级比值: {current_ratio_industrial:.4f}  (历史均值: {stats['均值_工业级']:.4f})")
#             print(f"   期货比值:   {current_ratio_futures:.4f}  (历史均值: {stats['均值_期货']:.4f})")
#
#             print(f"\n📊 Z-Score:")
#             print(f"   电池级 Z = {z_battery:+.4f}")
#             print(f"   工业级 Z = {z_industrial:+.4f}")
#             print(f"   期货 Z   = {z_futures:+.4f}")
#
#             print(f"\n🎯 综合偏离指数 (CDI): {cdi:+.4f}")
#             print(
#                 f"   权重配置: 电池级{WEIGHTS['电池级'] * 100:.0f}% + 工业级{WEIGHTS['工业级'] * 100:.0f}% + 期货{WEIGHTS['期货'] * 100:.0f}%")
#
#             # ===== 交易信号 =====
#             print("\n" + "!" * 80)
#             print(f"🚦 交易信号: {signal['signal']}")
#             print(f"   方向: {signal['direction']}")
#             print(f"   说明: {signal['description']}")
#             print(f"   建议: {signal['action']}")
#
#             # 信号强度指示
#             if signal['level'] == 'strong':
#                 if signal['direction'] == 'BUY':
#                     print("   💪 强烈看多信号，可考虑建立多头仓位")
#                 else:
#                     print("   💪 强烈看空信号，可考虑建立空头仓位或套保")
#             elif signal['level'] == 'moderate':
#                 print("   📊 轻度信号，建议轻仓参与")
#             else:
#                 print("   ⏸️ 观望等待更明确信号")
#             print("!" * 80)
#
#             # 显示历史CDI趋势（最近10次）
#             if len(history['cdi']) > 1:
#                 recent_cdi = history['cdi'][-10:]
#                 print(f"\n📉 最近CDI趋势: {', '.join([f'{x:+.2f}' for x in recent_cdi])}")
#
#                 # 判断趋势
#                 if len(recent_cdi) >= 3:
#                     trend = recent_cdi[-1] - recent_cdi[-3]
#                     if trend > 0.3:
#                         print(f"   📈 CDI持续上升 ({trend:+.2f})，偏离在扩大")
#                     elif trend < -0.3:
#                         print(f"   📉 CDI持续下降 ({trend:+.2f})，偏离在收敛")
#                     else:
#                         print(f"   ➡️ CDI相对平稳 ({trend:+.2f})")
#
#             print("=" * 80)
#
#             # 等待60秒后再次更新
#             time.sleep(60)
#
#     except KeyboardInterrupt:
#         print("\n\n⏹️ 用户手动停止监控")
#
#         # 生成监控报告
#         print("\n" + "=" * 80)
#         print("📋 监控报告")
#         print("=" * 80)
#
#         if len(history['cdi']) > 0:
#             print(f"\n监控时长: {len(history['cdi'])} 次更新")
#             print(f"最新CDI: {history['cdi'][-1]:+.4f}")
#             print(f"最新信号: {history['signal'][-1]}")
#
#             # 统计信号分布
#             signal_counts = {}
#             for s in history['signal']:
#                 signal_counts[s] = signal_counts.get(s, 0) + 1
#
#             print("\n信号分布:")
#             for s, count in signal_counts.items():
#                 print(f"   {s}: {count} 次 ({count / len(history['signal']) * 100:.1f}%)")
#
#             # 保存历史数据到CSV
#             history_df = pd.DataFrame(history)
#             history_df.to_csv('监控历史记录.csv', index=False, encoding='utf-8-sig')
#             print(f"\n📁 历史记录已保存: 监控历史记录.csv")
#
#     except Exception as e:
#         print(f"\n❌ 程序异常: {e}")
#         import traceback
#         traceback.print_exc()
#
# # ===================== 独立运行 =====================
# if __name__ == "__main__":
#     main()

# -*- coding: utf-8 -*-
"""
碳酸锂价格偏离度监控系统（四价格Z-Score模型）
功能：
1. 从Excel读取四个价格的历史数据，计算均值和标准差
2. 手动输入锂精矿、电池级、工业级现货价格
3. 自动获取碳酸锂主力合约实时价格（每分钟更新）
4. 计算四个价格的Z-Score，加权得到CDI，输出交易信号
5. CDI > 2.0 表示整体被高估（看空），CDI < -2.0 表示整体被低估（看多）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timedelta
import warnings
import os
import time
import re
import random
import akshare as ak
import json

warnings.filterwarnings('ignore')

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC', 'Heiti SC']
matplotlib.rcParams['axes.unicode_minus'] = False

# ===================== 配置参数 =====================
FILE_PATH = 'SMM_碳酸锂日度.xlsx'
SHEET_NAME = '价格数据'

# 指标列配置（四个价格）
PRICE_COLS = {
    '锂辉石精矿': 'B',
    '电池级碳酸锂': 'C',
    '工业级碳酸锂': 'D',
    '主力合约结算价': 'E'
}

# CDI权重配置（四个等权）
WEIGHTS = {
    '锂辉石精矿': 0.25,
    '电池级碳酸锂': 0.25,
    '工业级碳酸锂': 0.25,
    '主力合约结算价': 0.25
}

# 交易信号阈值
SIGNAL_THRESHOLDS = {
    'strong_bull': -2.0,   # < -2.0 强烈看多（价格整体被低估）
    'moderate_bull': -1.5, # -2.0 ~ -1.5 轻度看多
    'neutral_high': 1.5,   # -1.5 ~ 1.5 观望
    'moderate_bear': 1.5,  # 1.5 ~ 2.0 轻度看空
    'strong_bear': 2.0     # > 2.0 强烈看空（价格整体被高估）
}

# 期货品种映射（碳酸锂）
FUTURES_SYMBOL = 'LC0'  # 碳酸锂连续合约


# ===================== 数据读取模块 =====================
def read_excel_data(file_path, sheet_name):
    """
    从Excel读取四个价格指标的历史数据
    返回：日期列表和四个价格的数据字典
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    # 数据从第7行开始（索引7是2026-07-23）
    data_start = 7

    dates = []
    data_dict = {name: [] for name in PRICE_COLS.keys()}

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

        # 提取各价格数据
        for name, col in PRICE_COLS.items():
            col_idx = ord(col) - ord('A')
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


# ===================== 历史数据统计分析模块 =====================
def calculate_historical_stats(dates, data_dict):
    """
    计算四个价格的历史均值和标准差
    返回：四个价格的均值和标准差
    """
    # 创建DataFrame
    df = pd.DataFrame({
        'date': dates,
        '锂辉石精矿': data_dict['锂辉石精矿'],
        '电池级碳酸锂': data_dict['电池级碳酸锂'],
        '工业级碳酸锂': data_dict['工业级碳酸锂'],
        '主力合约结算价': data_dict['主力合约结算价']
    })

    # 去除无效数据（只要有一个价格缺失就剔除）
    df_clean = df.dropna(subset=['锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约结算价'])

    if len(df_clean) < 10:
        print("⚠️ 历史数据不足，请检查数据文件")
        return None

    # 计算均值和标准差
    stats = {
        '均值_锂辉石精矿': df_clean['锂辉石精矿'].mean(),
        '均值_电池级碳酸锂': df_clean['电池级碳酸锂'].mean(),
        '均值_工业级碳酸锂': df_clean['工业级碳酸锂'].mean(),
        '均值_主力合约结算价': df_clean['主力合约结算价'].mean(),
        '标准差_锂辉石精矿': df_clean['锂辉石精矿'].std(),
        '标准差_电池级碳酸锂': df_clean['电池级碳酸锂'].std(),
        '标准差_工业级碳酸锂': df_clean['工业级碳酸锂'].std(),
        '标准差_主力合约结算价': df_clean['主力合约结算价'].std(),
        '数据量': len(df_clean),
        '最新日期': df_clean['date'].iloc[-1],
        '历史价格_锂辉石精矿': df_clean['锂辉石精矿'].tolist(),
        '历史价格_电池级碳酸锂': df_clean['电池级碳酸锂'].tolist(),
        '历史价格_工业级碳酸锂': df_clean['工业级碳酸锂'].tolist(),
        '历史价格_主力合约结算价': df_clean['主力合约结算价'].tolist(),
    }

    print(f"\n📊 历史统计（基于 {stats['数据量']} 个交易日）")
    print(f"   最新日期: {stats['最新日期']}")
    print(f"\n   锂辉石精矿: 均值={stats['均值_锂辉石精矿']:.2f}, 标准差={stats['标准差_锂辉石精矿']:.2f}")
    print(f"   电池级碳酸锂: 均值={stats['均值_电池级碳酸锂']:.2f}, 标准差={stats['标准差_电池级碳酸锂']:.2f}")
    print(f"   工业级碳酸锂: 均值={stats['均值_工业级碳酸锂']:.2f}, 标准差={stats['标准差_工业级碳酸锂']:.2f}")
    print(f"   主力合约结算价: 均值={stats['均值_主力合约结算价']:.2f}, 标准差={stats['标准差_主力合约结算价']:.2f}")

    return stats


# ===================== 期货实时价格获取模块 =====================
def get_futures_realtime(contract_code='LC0'):
    """
    获取碳酸锂主力合约实时价格
    使用akshare获取
    """
    try:
        # 获取实时行情
        df = ak.futures_zh_realtime(symbol="碳酸锂")

        if df is None or df.empty:
            return None

        # 查找主力合约（按成交量排序取第一个）
        df_sorted = df.sort_values('volume', ascending=False)

        # 查找LC开头的合约
        lc_df = df_sorted[df_sorted['symbol'].str.startswith('LC')]

        if lc_df.empty:
            # 如果没有LC开头，尝试找碳酸锂相关
            lc_df = df_sorted[df_sorted['name'].str.contains('碳酸锂')]

        if lc_df.empty:
            # 使用第一个
            lc_df = df_sorted.head(1)

        row = lc_df.iloc[0]

        return {
            'symbol': row.get('symbol', ''),
            'price': float(row.get('trade', 0)),
            'open': float(row.get('open', 0)),
            'high': float(row.get('high', 0)),
            'low': float(row.get('low', 0)),
            'volume': int(row.get('volume', 0)),
            'position': int(row.get('position', 0)),
            'change_pct': float(row.get('changepercent', 0)),
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"⚠️ 获取期货价格失败: {e}")

        # 备用方案：尝试使用连续合约
        try:
            df = ak.futures_zh_minute_sina(symbol='LC0', period='1')
            if df is not None and not df.empty:
                last_row = df.iloc[-1]
                return {
                    'symbol': 'LC0',
                    'price': float(last_row.get('close', 0)),
                    'open': float(last_row.get('open', 0)),
                    'high': float(last_row.get('high', 0)),
                    'low': float(last_row.get('low', 0)),
                    'volume': int(last_row.get('volume', 0)),
                    'position': 0,
                    'change_pct': 0,
                    'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        except:
            pass

        return None


# ===================== 核心计算模块 =====================
def calculate_zscore(current_price, mean, std):
    """计算Z-Score"""
    if std is None or std == 0:
        return 0
    return (current_price - mean) / std


def calculate_cdi(z_ore, z_battery, z_industrial, z_futures, weights=None):
    """计算综合偏离指数CDI（四个价格等权）"""
    if weights is None:
        weights = WEIGHTS

    cdi = (weights['锂辉石精矿'] * z_ore +
           weights['电池级碳酸锂'] * z_battery +
           weights['工业级碳酸锂'] * z_industrial +
           weights['主力合约结算价'] * z_futures)
    return cdi


def get_trading_signal(cdi):
    """
    根据CDI值生成交易信号
    CDI > 2.0：四个价格整体高于历史均值 → 价格被高估 → 看空
    CDI < -2.0：四个价格整体低于历史均值 → 价格被低估 → 看多
    """
    if cdi > 2.0:
        return {
            'signal': '强烈看空',
            'direction': 'SELL',
            'level': 'strong',
            'description': '四个价格整体严重高估，强烈看空碳酸锂',
            'action': '空期货或套保'
        }
    elif cdi > 1.5:
        return {
            'signal': '轻度看空',
            'direction': 'SELL',
            'level': 'moderate',
            'description': '四个价格整体轻度高估，可轻仓试空',
            'action': '轻仓试空'
        }
    elif cdi >= -1.5:
        return {
            'signal': '观望',
            'direction': 'NEUTRAL',
            'level': 'neutral',
            'description': '四个价格处于正常区间，观望',
            'action': '观望'
        }
    elif cdi > -2.0:
        return {
            'signal': '轻度看多',
            'direction': 'BUY',
            'level': 'moderate',
            'description': '四个价格整体轻度低估，可轻仓试多',
            'action': '轻仓试多'
        }
    else:  # cdi <= -2.0
        return {
            'signal': '强烈看多',
            'direction': 'BUY',
            'level': 'strong',
            'description': '四个价格整体严重低估，强烈看多碳酸锂',
            'action': '多期货或现货'
        }


# ===================== 主程序 =====================
def main():
    print("=" * 80)
    print("🔬 碳酸锂价格偏离度监控系统（四价格Z-Score模型）")
    print("=" * 80)
    print("\n功能说明:")
    print("  1. 从Excel读取四个价格的历史数据，计算均值和标准差")
    print("  2. 手动输入锂精矿、电池级、工业级现货价格")
    print("  3. 自动获取碳酸锂主力合约实时价格（每分钟更新）")
    print("  4. 计算四个价格的Z-Score，等权加权得到CDI")
    print("  5. CDI > 2.0 → 高估看空 | CDI < -2.0 → 低估看多")
    print("=" * 80)

    # -------------------- 第一步：读取历史数据 --------------------
    print("\n📂 [1/4] 读取历史数据...")
    try:
        dates, data_dict = read_excel_data(FILE_PATH, SHEET_NAME)
        print(f"✅ 读取成功，共 {len(dates)} 个交易日")
        print(f"   日期范围: {dates[0]} ~ {dates[-1]}")
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return

    # -------------------- 第二步：计算历史统计 --------------------
    print("\n📊 [2/4] 计算历史统计...")
    stats = calculate_historical_stats(dates, data_dict)
    if stats is None:
        print("❌ 历史统计计算失败")
        return

    # 显示历史价格分布
    print("\n📈 历史价格统计:")
    print(f"   锂辉石精矿: 均值={stats['均值_锂辉石精矿']:.2f}, 标准差={stats['标准差_锂辉石精矿']:.2f}")
    print(f"   电池级碳酸锂: 均值={stats['均值_电池级碳酸锂']:.2f}, 标准差={stats['标准差_电池级碳酸锂']:.2f}")
    print(f"   工业级碳酸锂: 均值={stats['均值_工业级碳酸锂']:.2f}, 标准差={stats['标准差_工业级碳酸锂']:.2f}")
    print(f"   主力合约结算价: 均值={stats['均值_主力合约结算价']:.2f}, 标准差={stats['标准差_主力合约结算价']:.2f}")

    # -------------------- 第三步：手动输入现货价格 --------------------
    print("\n💵 [3/4] 输入现货价格")
    print("-" * 40)
    print("注: 锂精矿价格为美元/吨，碳酸锂价格为元/吨")
    print("-" * 40)

    try:
        ore_price = float(input("请输入锂精矿价格 (美元/吨): ").strip())
        battery_price = float(input("请输入电池级碳酸锂价格 (元/吨): ").strip())
        industrial_price = float(input("请输入工业级碳酸锂价格 (元/吨): ").strip())
    except ValueError:
        print("❌ 输入格式错误，请输入数字")
        return

    print(f"\n✅ 输入确认:")
    print(f"   锂精矿: {ore_price:.2f} 美元/吨")
    print(f"   电池级碳酸锂: {battery_price:.2f} 元/吨")
    print(f"   工业级碳酸锂: {industrial_price:.2f} 元/吨")

    # -------------------- 第四步：实时监控 --------------------
    print("\n🔄 [4/4] 开始实时监控...")
    print("=" * 80)
    print("按 Ctrl+C 停止监控")
    print("=" * 80)

    # 计算现货端的Z-Score
    z_ore = calculate_zscore(ore_price, stats['均值_锂辉石精矿'], stats['标准差_锂辉石精矿'])
    z_battery = calculate_zscore(battery_price, stats['均值_电池级碳酸锂'], stats['标准差_电池级碳酸锂'])
    z_industrial = calculate_zscore(industrial_price, stats['均值_工业级碳酸锂'], stats['标准差_工业级碳酸锂'])

    print(f"\n📊 现货端Z-Score:")
    print(f"   锂辉石精矿 Z = {z_ore:+.4f}")
    print(f"   电池级碳酸锂 Z = {z_battery:+.4f}")
    print(f"   工业级碳酸锂 Z = {z_industrial:+.4f}")

    # 初始化历史记录用于绘图
    history = {
        'time': [],
        'futures_price': [],
        'z_futures': [],
        'cdi': [],
        'signal': []
    }

    update_count = 0

    try:
        while True:
            # 获取期货实时价格
            futures_data = get_futures_realtime()

            if futures_data is None or futures_data['price'] <= 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取期货价格失败，等待重试...")
                time.sleep(10)
                continue

            futures_price = futures_data['price']

            # 计算期货Z-Score
            z_futures = calculate_zscore(futures_price, stats['均值_主力合约结算价'], stats['标准差_主力合约结算价'])

            # 计算CDI（四个价格等权）
            cdi = calculate_cdi(z_ore, z_battery, z_industrial, z_futures)

            # 获取交易信号
            signal = get_trading_signal(cdi)

            # 记录历史
            update_count += 1
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            history['time'].append(current_time)
            history['futures_price'].append(futures_price)
            history['z_futures'].append(z_futures)
            history['cdi'].append(cdi)
            history['signal'].append(signal['signal'])

            # ===== 输出结果 =====
            print("\n" + "=" * 80)
            print(f"🕐 更新时间: {current_time}  (第{update_count}次更新)")
            print("=" * 80)

            print(f"\n📈 期货行情:")
            print(f"   主力合约: {futures_data.get('symbol', 'N/A')}")
            print(f"   最新价: {futures_price:.2f} 元/吨")
            print(f"   涨跌幅: {futures_data.get('change_pct', 0):+.2f}%")
            print(f"   成交量: {futures_data.get('volume', 0):,}")

            print(f"\n📊 Z-Score:")
            print(f"   锂辉石精矿 Z = {z_ore:+.4f}  (历史均值: {stats['均值_锂辉石精矿']:.2f}, 标准差: {stats['标准差_锂辉石精矿']:.2f})")
            print(f"   电池级碳酸锂 Z = {z_battery:+.4f}  (历史均值: {stats['均值_电池级碳酸锂']:.2f}, 标准差: {stats['标准差_电池级碳酸锂']:.2f})")
            print(f"   工业级碳酸锂 Z = {z_industrial:+.4f}  (历史均值: {stats['均值_工业级碳酸锂']:.2f}, 标准差: {stats['标准差_工业级碳酸锂']:.2f})")
            print(f"   主力合约结算价 Z = {z_futures:+.4f}  (历史均值: {stats['均值_主力合约结算价']:.2f}, 标准差: {stats['标准差_主力合约结算价']:.2f})")

            print(f"\n🎯 综合偏离指数 (CDI): {cdi:+.4f}")
            print(f"   权重配置: 锂辉石精矿25% + 电池级25% + 工业级25% + 期货25%")

            # ===== 交易信号 =====
            print("\n" + "!" * 80)
            print(f"🚦 交易信号: {signal['signal']}")
            print(f"   方向: {signal['direction']}")
            print(f"   说明: {signal['description']}")
            print(f"   建议: {signal['action']}")

            # 信号强度指示
            if signal['level'] == 'strong':
                if signal['direction'] == 'BUY':
                    print("   💪 强烈看多信号，可考虑建立多头仓位")
                else:
                    print("   💪 强烈看空信号，可考虑建立空头仓位或套保")
            elif signal['level'] == 'moderate':
                print("   📊 轻度信号，建议轻仓参与")
            else:
                print("   ⏸️ 观望等待更明确信号")
            print("!" * 80)

            # 显示历史CDI趋势（最近10次）
            if len(history['cdi']) > 1:
                recent_cdi = history['cdi'][-10:]
                print(f"\n📉 最近CDI趋势: {', '.join([f'{x:+.2f}' for x in recent_cdi])}")

                # 判断趋势
                if len(recent_cdi) >= 3:
                    trend = recent_cdi[-1] - recent_cdi[-3]
                    if trend > 0.3:
                        print(f"   📈 CDI持续上升 ({trend:+.2f})，高估在扩大，看空信号增强")
                    elif trend < -0.3:
                        print(f"   📉 CDI持续下降 ({trend:+.2f})，低估在加深，看多信号增强")
                    else:
                        print(f"   ➡️ CDI相对平稳 ({trend:+.2f})")

            print("=" * 80)

            # 等待60秒后再次更新
            time.sleep(60)

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户手动停止监控")

        # 生成监控报告
        print("\n" + "=" * 80)
        print("📋 监控报告")
        print("=" * 80)

        if len(history['cdi']) > 0:
            print(f"\n监控时长: {len(history['cdi'])} 次更新")
            print(f"最新CDI: {history['cdi'][-1]:+.4f}")
            print(f"最新信号: {history['signal'][-1]}")

            # 统计信号分布
            signal_counts = {}
            for s in history['signal']:
                signal_counts[s] = signal_counts.get(s, 0) + 1

            print("\n信号分布:")
            for s, count in signal_counts.items():
                print(f"   {s}: {count} 次 ({count / len(history['signal']) * 100:.1f}%)")

            # 保存历史数据到CSV
            history_df = pd.DataFrame(history)
            history_df.to_csv('监控历史记录_四价格模型.csv', index=False, encoding='utf-8-sig')
            print(f"\n📁 历史记录已保存: 监控历史记录_四价格模型.csv")

    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()


# ===================== 独立运行 =====================
if __name__ == "__main__":
    main()