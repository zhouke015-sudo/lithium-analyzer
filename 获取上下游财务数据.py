# -*- coding: utf-8 -*-
"""
紫金矿业和宁德时代财务数据自动填充脚本
直接修改 SMM_碳酸锂日度.xlsx 文件的 紫金矿业 和 宁德时代 Sheet
从2023Q4到当前日期前一个季度自动提取数据，按季度从近到远排序
仅填充缺失的数据
"""

import os
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# -------------------------- 全局配置 --------------------------
# 目标Excel文件（与脚本同目录）
EXCEL_FILE = "SMM_碳酸锂日度.xlsx"

# 目标公司配置
COMPANIES = [
    {"code": "601899", "name": "紫金矿业", "sheet": "紫金矿业"},
    {"code": "300750", "name": "宁德时代", "sheet": "宁德时代"}
]

# 列配置
FINAL_COLUMNS = [
    "净利润-同比增长",
    "净资产收益率",
    "净利率",
    "每股收益",
    "营业总收入-同比增长",
    "销售毛利率",
    "每股经营现金流量",
    "资产负债率"
]


# -------------------------- 工具函数 --------------------------

def get_quarter_list():
    """
    获取从2023Q4到当前日期前一个季度的所有季度列表
    自动计算当前日期，动态决定目标季度
    """
    quarter_list = []

    # 从2023Q4开始
    start_year = 2023
    start_quarter = 4

    # 获取当前日期
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # 计算当前季度
    current_quarter = (current_month - 1) // 3 + 1

    # 计算目标季度：当前季度的前一个季度
    target_year = current_year
    target_quarter = current_quarter - 1

    # 如果当前是Q1，则目标为上一年的Q4
    if target_quarter == 0:
        target_year -= 1
        target_quarter = 4

    # 确保目标不早于2023Q4
    if target_year < 2023 or (target_year == 2023 and target_quarter < 4):
        print(f"⚠️ 目标季度 {target_year}Q{target_quarter} 早于2023Q4，将使用2023Q4作为起始")
        target_year = 2023
        target_quarter = 4

    print(f"📅 当前日期: {now.strftime('%Y-%m-%d')}")
    print(f"📅 当前季度: {current_year}Q{current_quarter}")
    print(f"📅 目标季度(前一个季度): {target_year}Q{target_quarter}")

    # 生成从2023Q4到目标季度的所有季度
    year = start_year
    q = start_quarter

    while year < target_year or (year == target_year and q <= target_quarter):
        quarter_str = f"{year}Q{q}"
        # 计算季度对应的日期
        if q == 1:
            date_str = f"{year}0331"
        elif q == 2:
            date_str = f"{year}0630"
        elif q == 3:
            date_str = f"{year}0930"
        else:  # q == 4
            date_str = f"{year}1231"

        quarter_list.append({
            "quarter": quarter_str,
            "date": date_str
        })

        # 下一个季度
        q += 1
        if q > 4:
            q = 1
            year += 1

    # 按季度从近到远排序（新季度在前）
    quarter_list.reverse()

    return quarter_list


def clean_percent(val):
    """清理百分比值"""
    if pd.isna(val) or val == "-" or val == "":
        return np.nan
    if isinstance(val, str):
        val = val.replace("%", "").replace(",", "").strip()
        try:
            return float(val)
        except:
            return np.nan
    try:
        return float(val)
    except:
        return np.nan


def get_quarter_from_date(date_str):
    """从日期字符串获取季度"""
    try:
        dt = pd.to_datetime(date_str)
        year = dt.year
        month = dt.month
        quarter = (month - 1) // 3 + 1
        return f"{year}Q{quarter}"
    except:
        return None


def find_quarter_row(df, quarter, company_name):
    """在DataFrame中查找指定季度的行索引"""
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[0]) and str(row.iloc[0]) == quarter:
            return idx
    return None


# -------------------------- 核心数据采集函数 --------------------------

def get_financial_data(code, quarter_info):
    """
    获取指定季度的财务数据
    返回: dict
    """
    quarter = quarter_info["quarter"]
    date_str = quarter_info["date"]

    result = {col: np.nan for col in FINAL_COLUMNS}
    result["_quarter"] = quarter
    result["_has_report"] = False
    result["_report_status"] = ""

    # -------------------------- 1. 获取业绩报表数据 --------------------------
    try:
        df_yjbb = ak.stock_yjbb_em(date=date_str)
        if df_yjbb is not None and not df_yjbb.empty:
            df_yjbb["股票代码"] = df_yjbb["股票代码"].astype(str).apply(lambda x: x.zfill(6) if x.isdigit() else x)
            stock_data = df_yjbb[df_yjbb["股票代码"] == code]

            if not stock_data.empty:
                row = stock_data.iloc[0]
                result["_has_report"] = True

                # 提取各项指标
                col_mapping = {
                    "每股收益": "每股收益",
                    "营业总收入-同比增长": "营业总收入-同比增长",
                    "净利润-同比增长": "净利润-同比增长",
                    "净资产收益率": "净资产收益率"
                }

                for col_key, col_name in col_mapping.items():
                    if col_key in row.index and pd.notna(row[col_key]):
                        try:
                            val = float(row[col_key])
                            result[col_name] = round(val, 2) if pd.notna(val) else np.nan
                        except:
                            pass

                # 销售毛利率
                if "销售毛利率" in row.index and pd.notna(row["销售毛利率"]):
                    try:
                        result["销售毛利率"] = round(float(row["销售毛利率"]), 2)
                    except:
                        pass
                elif "毛利率" in row.index and pd.notna(row["毛利率"]):
                    try:
                        result["销售毛利率"] = round(float(row["毛利率"]), 2)
                    except:
                        pass

                # 每股经营现金流量
                if "每股经营现金流量" in row.index and pd.notna(row["每股经营现金流量"]):
                    try:
                        result["每股经营现金流量"] = round(float(row["每股经营现金流量"]), 2)
                    except:
                        pass
            else:
                result["_report_status"] = "该季度暂无财报"
        else:
            result["_report_status"] = "该季度暂无财报"

    except Exception as e:
        result["_report_status"] = f"获取失败: {str(e)[:30]}"

    # -------------------------- 2. 获取净利率/资产负债率 --------------------------
    try:
        df_fin_abs = ak.stock_financial_abstract_ths(symbol=code, indicator="按单季度")

        if df_fin_abs is not None and not df_fin_abs.empty:
            df_fin_abs["季度"] = df_fin_abs["报告期"].apply(
                lambda x: get_quarter_from_date(str(x)) if pd.notna(x) else None)
            df_fin_abs = df_fin_abs.dropna(subset=["季度"])

            q_data = df_fin_abs[df_fin_abs["季度"] == quarter]
            if not q_data.empty:
                row = q_data.iloc[0]
                if "销售净利率" in row.index:
                    val = clean_percent(row.get("销售净利率"))
                    if pd.notna(val):
                        result["净利率"] = round(val, 2)

                if "资产负债率" in row.index:
                    val = clean_percent(row.get("资产负债率"))
                    if pd.notna(val):
                        result["资产负债率"] = round(val, 2)
    except Exception as e:
        pass

    return result


# -------------------------- 核心处理函数 --------------------------

def process_company(company_info):
    """处理单个公司的所有季度数据"""
    code = company_info["code"]
    name = company_info["name"]
    sheet_name = company_info["sheet"]

    print(f"\n{'=' * 60}")
    print(f"🏢 处理: {code} - {name} (Sheet: {sheet_name})")
    print(f"{'=' * 60}")

    # 1. 检查Excel文件是否存在
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ 文件不存在: {EXCEL_FILE}")
        print(f"   请确保 {EXCEL_FILE} 与脚本在同一目录下")
        return 0

    print(f"📄 读取文件: {EXCEL_FILE}")

    # 2. 读取对应的Sheet
    try:
        df_sheet = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=0, engine="openpyxl")
        print(f"   {sheet_name} 读取成功，共 {len(df_sheet)} 行")
        print(f"   列名: {list(df_sheet.columns)}")
    except Exception as e:
        print(f"❌ 读取{sheet_name}失败: {str(e)}")
        return 0

    # 3. 获取列名（第一列是季度，后面是各指标）
    col_names = list(df_sheet.columns)
    if len(col_names) < 2:
        print(f"❌ {sheet_name} 列数不足，请检查格式")
        return 0

    # 第一列是季度
    quarter_col = col_names[0]
    # 指标列从第2列开始
    data_cols = col_names[1:]

    print(f"   📊 季度列: {quarter_col}")
    print(f"   📊 指标列: {data_cols}")

    # 4. 获取季度列表
    quarter_list = get_quarter_list()
    if quarter_list:
        print(f"📅 目标季度范围: {quarter_list[-1]['quarter']} 到 {quarter_list[0]['quarter']}")
        print(f"   共 {len(quarter_list)} 个季度")
    else:
        print("⚠️ 没有获取到有效季度")
        return 0

    # 5. 构建现有季度数据字典
    existing_data = {}
    for idx, row in df_sheet.iterrows():
        quarter_val = row.iloc[0]  # 第一列是季度
        if pd.notna(quarter_val) and str(quarter_val) != "":
            quarter_str = str(quarter_val)
            existing_data[quarter_str] = idx

    print(f"   📍 现有季度数: {len(existing_data)}")

    # 6. 逐季度检查并采集数据
    success_count = 0
    skip_count = 0
    update_count = 0

    for q_info in quarter_list:
        quarter = q_info["quarter"]

        # 检查该季度是否已存在
        if quarter in existing_data:
            row_idx = existing_data[quarter]
            row = df_sheet.iloc[row_idx]

            # 检查哪些列需要填充（从第2列开始）
            need_fill_cols = []
            for i, col in enumerate(data_cols):
                if i + 1 < len(row):
                    val = row.iloc[i + 1]
                    if pd.isna(val) or val == "" or val == " ":
                        need_fill_cols.append(col)

            if not need_fill_cols:
                skip_count += 1
                print(f"  ⏭️ {quarter} 数据完整，跳过")
                continue
            else:
                print(f"  📊 {quarter} 部分数据缺失({len(need_fill_cols)}项)，采集补充...")
                result = get_financial_data(code, q_info)

                has_update = False
                for col in need_fill_cols:
                    if col in result and pd.notna(result[col]):
                        col_idx = data_cols.index(col) + 1  # +1 因为第0列是季度
                        df_sheet.iloc[row_idx, col_idx] = result[col]
                        has_update = True
                        success_count += 1
                if has_update:
                    update_count += 1
                    print(f"    ✅ 补充成功")
                else:
                    print(f"    ⚠️ 未能获取到新数据")
                continue

        # 该季度不存在，添加新行
        print(f"  📊 {quarter} 无数据，采集...")
        result = get_financial_data(code, q_info)

        # 创建新行
        new_row = [quarter]
        for col in data_cols:
            if col in result and pd.notna(result[col]):
                new_row.append(result[col])
            else:
                new_row.append(np.nan)

        # 添加到DataFrame
        df_sheet.loc[len(df_sheet)] = new_row
        existing_data[quarter] = len(df_sheet) - 1

        # 检查是否有有效数据
        has_data = any(pd.notna(v) for v in new_row[1:] if v != "")
        if has_data:
            success_count += 1
            update_count += 1
            print(f"    ✅ 数据采集成功")
        else:
            print(f"    ⚠️ 未获取到有效数据")

    print(f"   📊 统计: 成功 {success_count} 项, 跳过 {skip_count} 个季度, 更新 {update_count} 个季度")

    # 7. 按季度从近到远排序
    # 按季度列排序
    quarter_order = {q["quarter"]: i for i, q in enumerate(quarter_list)}

    # 获取所有有效行
    valid_rows = []
    for idx, row in df_sheet.iterrows():
        quarter_val = row.iloc[0]
        if pd.notna(quarter_val) and str(quarter_val) != "":
            q_str = str(quarter_val)
            if q_str in quarter_order:
                valid_rows.append((idx, q_str, quarter_order[q_str]))

    # 按季度顺序排序（从近到远，即权重从小到大）
    sorted_rows = sorted(valid_rows, key=lambda x: x[2])

    if sorted_rows:
        # 重新排列行
        sorted_indices = [x[0] for x in sorted_rows]
        df_sheet = df_sheet.loc[sorted_indices].reset_index(drop=True)

    # 8. 保存文件
    try:
        # 读取所有sheet
        all_sheets = {}
        xl = pd.ExcelFile(EXCEL_FILE)
        for sheet in xl.sheet_names:
            if sheet != sheet_name:
                all_sheets[sheet] = pd.read_excel(EXCEL_FILE, sheet_name=sheet, engine="openpyxl")

        # 用新的数据替换
        all_sheets[sheet_name] = df_sheet

        # 重新写入
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
            for sheet, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet, index=False)

        print(f"✅ {name} 处理完成，数据已保存到 {EXCEL_FILE}")
    except Exception as e:
        print(f"❌ 保存失败: {str(e)}")
        return 0

    return success_count


# -------------------------- 主函数 --------------------------

def main():
    print("=" * 80)
    print("📊 紫金矿业和宁德时代财务数据自动填充工具")
    print(f"📁 工作目录: {os.getcwd()}")
    print(f"📄 目标文件: {EXCEL_FILE}")

    # 检查文件是否存在
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ 错误: 找不到文件 {EXCEL_FILE}")
        print(f"   请确保 {EXCEL_FILE} 与脚本在同一目录下")
        return

    # 获取季度范围
    quarter_list = get_quarter_list()
    if quarter_list:
        print(f"📅 数据范围: {quarter_list[-1]['quarter']} 到 {quarter_list[0]['quarter']}")
        print(f"   共 {len(quarter_list)} 个季度")
    else:
        print("📅 数据范围: 无有效季度")

    print(
        "📊 指标: 净利润-同比增长, 净资产收益率, 净利率, 每股收益, 营业总收入-同比增长, 销售毛利率, 每股经营现金流量, 资产负债率")
    print("=" * 80)

    total_success = 0

    for company in COMPANIES:
        success = process_company(company)
        if success > 0:
            total_success += success

    print("\n" + "=" * 80)
    print("🎉 全部处理完成！")
    print(f"📊 总计成功采集: {total_success} 项数据")
    print("=" * 80)


# -------------------------- 执行 --------------------------
if __name__ == "__main__":
    main()