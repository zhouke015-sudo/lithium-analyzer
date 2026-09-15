# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# import seaborn as sns
# from sklearn.preprocessing import StandardScaler
# from sklearn.neighbors import KNeighborsClassifier
# from sklearn.model_selection import LeaveOneOut
# from sklearn.metrics import confusion_matrix, classification_report
# import warnings
#
# warnings.filterwarnings('ignore')
#
# # ==================== 1. 数据加载 ====================
# file_path = '/Users/hanxin/Desktop/SMM_碳酸锂.xlsx'
#
# # 🔥 关键：header=None，然后手动提取列名
# raw = pd.read_excel(file_path, sheet_name='供需平衡表', header=None)
#
# # 第1行是指标名称（索引0），第4行开始是数据（索引4起）
# col_names = ['日期'] + [str(x) for x in raw.iloc[0, 1:].values]
# df = raw.iloc[4:].reset_index(drop=True)
# df.columns = col_names
#
# print("=" * 90)
# print("数据加载完成")
# print("=" * 90)
# print(f"供需平衡表: {df.shape[0]} 行, {df.shape[1]} 列")
# print(f"\n列名列表:")
# for i, c in enumerate(df.columns, 1):
#     print(f"  {i}. {c}")
#
# # 转换日期和数值
# df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
# df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)
#
# for col in df.columns[1:]:
#     df[col] = pd.to_numeric(df[col], errors='coerce')
#
#
# # 添加季度
# def parse_quarter(date):
#     return f"{date.year}Q{(date.month - 1) // 3 + 1}"
#
#
# df['季度'] = df['日期'].apply(parse_quarter)
#
# print(f"\n数据日期范围: {df['日期'].min()} ~ {df['日期'].max()}")
#
# # ==================== 2. 找结算价列 ====================
# settle_cols = [c for c in df.columns if ('主力合约' in c and '结算价' in c)]
# print(f"\n结算价列: {settle_cols}")
#
# if not settle_cols:
#     # 备用：找含"结算价"的列
#     settle_cols = [c for c in df.columns if '结算价' in c]
#     print(f"备用查找: {settle_cols}")
#
# settle_col = settle_cols[0]
# print(f"使用结算价列: {settle_col}")
#
# # ==================== 3. 按季度聚合 ====================
# indicator_cols = [c for c in df.columns if c not in ['日期', '季度']]
#
# quarterly_df = df.groupby('季度').agg({
#     col: lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
#     for col in indicator_cols
# }).reset_index()
#
# print(f"\n季度聚合完成，共 {len(quarterly_df)} 个季度")
# print(f"季度列表: {quarterly_df['季度'].tolist()}")
#
# # ==================== 4. 处理紫金矿业和宁德时代 ====================
# zj_df = pd.read_excel(file_path, sheet_name='紫金矿业', header=0)
# nd_df = pd.read_excel(file_path, sheet_name='宁德时代', header=0)
#
# zj_df['季度'] = zj_df['季度'].astype(str)
# nd_df['季度'] = nd_df['季度'].astype(str)
#
# zj_cols = ['净利润-同比增长', '净资产收益率', '净利率', '每股收益',
#            '营业总收入-同比增长', '销售毛利率', '每股经营现金流量', '资产负债率']
# nd_cols = zj_cols.copy()
#
# zj_df_r = zj_df.rename(columns={c: f'紫金_{c}' for c in zj_cols})
# nd_df_r = nd_df.rename(columns={c: f'宁德_{c}' for c in nd_cols})
#
# # ==================== 5. 合并 ====================
# merged = quarterly_df.merge(zj_df_r, on='季度', how='inner')
# merged = merged.merge(nd_df_r, on='季度', how='inner')
#
# print(f"\n合并后数据: {len(merged)} 个季度")
# print(f"季度: {merged['季度'].tolist()}")
#
#
# # ==================== 6. 生成标签 ====================
# def get_quarter_label(quarter):
#     q_data = df[df['季度'] == quarter].sort_values('日期').dropna(subset=[settle_col])
#     if len(q_data) < 2:
#         return np.nan
#     first = q_data.iloc[0][settle_col]
#     last = q_data.iloc[-1][settle_col]
#     return 1 if last > first else 0
#
#
# merged['标签'] = merged['季度'].apply(get_quarter_label)
# merged = merged.dropna(subset=['标签'])
# merged['标签'] = merged['标签'].astype(int)
#
# print(f"\n标签生成完成: {len(merged)} 条")
# print(f"标签分布: 空头(0)={sum(merged['标签'] == 0)}, 多头(1)={sum(merged['标签'] == 1)}")
#
# # 显示各季度标签详情
# print("\n各季度标签详情:")
# print(f"{'季度':<10} {'首日':>8} {'末日':>8} {'方向':<6}")
# print("-" * 40)
# for _, row in merged.iterrows():
#     q = row['季度']
#     q_data = df[df['季度'] == q].sort_values('日期').dropna(subset=[settle_col])
#     first = q_data.iloc[0][settle_col]
#     last = q_data.iloc[-1][settle_col]
#     direction = "多头" if row['标签'] == 1 else "空头"
#     print(f"{q:<10} {first:>8.0f} {last:>8.0f} {direction:<6}")
#
# # ==================== 7. 定义特征列 ====================
# supply_cols = [c for c in indicator_cols if c != settle_col]
# feature_cols = supply_cols + [f'紫金_{c}' for c in zj_cols] + [f'宁德_{c}' for c in nd_cols]
#
# print(f"\n总特征数: {len(feature_cols)}")
# print(f"  供需平衡表特征: {len(supply_cols)}")
# print(f"  紫金矿业: {len(zj_cols)}")
# print(f"  宁德时代: {len(nd_cols)}")
#
# # 填充缺失值
# for col in feature_cols:
#     if merged[col].isnull().any():
#         merged[col] = merged[col].fillna(merged[col].mean())
#
# # ==================== 8. 相关性分析 ====================
# print("\n" + "=" * 90)
# print("【相关性分析】")
# print("=" * 90)
#
# correlations = {}
# for col in feature_cols:
#     r = merged[col].corr(merged['标签'])
#     r_price = merged[col].corr(merged[settle_col])
#     correlations[col] = {'vs_标签': r, 'vs_结算价': r_price}
#
# corr_df = pd.DataFrame([
#     {'特征': c, 'vs_标签': v['vs_标签'], 'vs_结算价': v['vs_结算价'],
#      '绝对值': abs(v['vs_标签'])}
#     for c, v in correlations.items()
# ]).sort_values('绝对值', ascending=False)
#
# print(f"\n{'排名':<4} {'特征':<50} {'vs标签':<10} {'vs结算价':<10} {'方向'}")
# print("-" * 95)
# for i, (_, row) in enumerate(corr_df.iterrows(), 1):
#     direction = "正" if row['vs_标签'] > 0 else "负"
#     print(f"{i:<4} {row['特征'][:49]:<50} {row['vs_标签']:>8.3f}  {row['vs_结算价']:>8.3f}   {direction}")
#
# # ==================== 9. KNN留一法 ====================
# print("\n" + "=" * 90)
# print("【KNN留一法预测】")
# print("=" * 90)
#
# X = merged[feature_cols].values
# y = merged['标签'].values
# quarters = merged['季度'].tolist()
#
# scaler = StandardScaler()
# X_scaled = scaler.fit_transform(X)
#
# loo = LeaveOneOut()
# predictions, actuals, pred_quarters = [], [], []
#
# for train_idx, test_idx in loo.split(X_scaled):
#     X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
#     y_tr, y_te = y[train_idx], y[test_idx]
#
#     k = min(5, len(X_tr))
#     knn = KNeighborsClassifier(n_neighbors=k)
#     knn.fit(X_tr, y_tr)
#     pred = knn.predict(X_te)[0]
#
#     predictions.append(pred)
#     actuals.append(y_te[0])
#     pred_quarters.append(quarters[test_idx[0]])
#
# correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
# total = len(predictions)
#
# print(f"\n{'季度':<10} {'预测':<6} {'实际':<6} {'结果'}")
# print("-" * 40)
# for q, p, a in zip(pred_quarters, predictions, actuals):
#     p_dir = "多头" if p == 1 else "空头"
#     a_dir = "多头" if a == 1 else "空头"
#     result = "✅" if p == a else "❌"
#     print(f"{q:<10} {p_dir:<6} {a_dir:<6} {result}")
#
# print(f"\n准确率: {correct}/{total} = {correct / total:.2%}")
# print(f"\n混淆矩阵:")
# print(confusion_matrix(actuals, predictions))
# print(f"\n分类报告:")
# print(classification_report(actuals, predictions, target_names=['空头', '多头'], zero_division=0))
#
# # ==================== 10. 可视化 ====================
# try:
#     plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC']
#     plt.rcParams['axes.unicode_minus'] = False
#
#     fig, ax = plt.subplots(figsize=(12, 10))
#     top20 = corr_df.head(20)
#     colors = ['green' if v > 0 else 'red' for v in top20['vs_标签']]
#     ax.barh(range(len(top20)), top20['vs_标签'].values, color=colors)
#     ax.set_yticks(range(len(top20)))
#     ax.set_yticklabels([c[:45] for c in top20['特征'].values])
#     ax.axvline(x=0, color='black', linewidth=0.8)
#     ax.set_xlabel('与标签的相关系数')
#     ax.set_title('Top 20 特征与碳酸锂期货涨跌的相关性')
#     plt.tight_layout()
#     plt.savefig('/Users/hanxin/Desktop/特征相关性_Top20.png', dpi=150, bbox_inches='tight')
#     print("\n✅ 已保存: 特征相关性_Top20.png")
#     plt.close('all')
# except Exception as e:
#     print(f"⚠️ 绘图失败: {e}")
#
# # ==================== 11. 报告 ====================
# print("\n" + "=" * 90)
# print("【分析报告摘要】")
# print("=" * 90)
#
# print(f"""
# 一、数据概况
#    季度数: {len(merged)} ({merged['季度'].iloc[0]} ~ {merged['季度'].iloc[-1]})
#    特征数: {len(feature_cols)}
#      - 供需平衡表: {len(supply_cols)} 个
#      - 紫金矿业: {len(zj_cols)} 个
#      - 宁德时代: {len(nd_cols)} 个
#
# 二、相关性最强 Top 10
# """)
# for i, (_, row) in enumerate(corr_df.head(10).iterrows(), 1):
#     direction = "正相关" if row['vs_标签'] > 0 else "负相关"
#     print(f"   {i}. {row['特征'][:50]}: {row['vs_标签']:.3f} ({direction})")
#
# print(f"""
# 三、KNN预测
#    准确率: {correct}/{total} = {correct / total:.2%}
#    空头正确: {sum(1 for p, a in zip(predictions, actuals) if a == 0 and p == 0)}/{sum(1 for a in actuals if a == 0)}
#    多头正确: {sum(1 for p, a in zip(predictions, actuals) if a == 1 and p == 1)}/{sum(1 for a in actuals if a == 1)}
# """)
#
# strong_pos = corr_df[corr_df['vs_标签'] > 0.3]
# strong_neg = corr_df[corr_df['vs_标签'] < -0.3]
#
# print(f"四、强正相关 ({len(strong_pos)}个):")
# for _, row in strong_pos.iterrows():
#     print(f"   ✅ {row['特征'][:55]}: {row['vs_标签']:.3f}")
#
# print(f"\n五、强负相关 ({len(strong_neg)}个):")
# for _, row in strong_neg.iterrows():
#     print(f"   ❌ {row['特征'][:55]}: {row['vs_标签']:.3f}")
#
# print("\n" + "=" * 90)
# print("分析完成!")
# print("=" * 90)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import confusion_matrix, classification_report
import warnings

warnings.filterwarnings('ignore')

# ==================== 1. 数据加载 ====================
file_path = '/Users/hanxin/Desktop/SMM_碳酸锂.xlsx'

raw = pd.read_excel(file_path, sheet_name='供需平衡表', header=None)
col_names = ['日期'] + [str(x) for x in raw.iloc[0, 1:].values]
df = raw.iloc[4:].reset_index(drop=True)
df.columns = col_names

print("=" * 90)
print("数据加载完成")
print("=" * 90)

# 转换日期和数值
df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
df = df.dropna(subset=['日期']).sort_values('日期').reset_index(drop=True)

for col in df.columns[1:]:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 🔥 需求、出口量转为正值
demand_col = [c for c in df.columns if '需求' in c]
export_col = [c for c in df.columns if '出口量' in c]

if demand_col:
    df[demand_col[0]] = df[demand_col[0]].abs()
    print(f"✅ 需求列已转为正值: {demand_col[0]}")
if export_col:
    df[export_col[0]] = df[export_col[0]].abs()
    print(f"✅ 出口量列已转为正值: {export_col[0]}")

# 添加月份和季度
df['月份'] = df['日期'].dt.to_period('M').astype(str)
df['季度'] = df['日期'].apply(lambda d: f"{d.year}Q{(d.month - 1) // 3 + 1}")

print(f"数据日期范围: {df['日期'].min()} ~ {df['日期'].max()}")

# ==================== 2. 找结算价列 ====================
settle_cols = [c for c in df.columns if ('主力合约' in c and '结算价' in c)]
settle_col = settle_cols[0]
print(f"使用结算价列: {settle_col}")

# ==================== 3. 按月聚合 ====================
indicator_cols = [c for c in df.columns if c not in ['日期', '月份', '季度']]

monthly_df = df.groupby('月份').agg({
    col: lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
    for col in indicator_cols
}).reset_index()

monthly_df['季度'] = monthly_df['月份'].apply(
    lambda m: f"{int(m.split('-')[0])}Q{(int(m.split('-')[1]) - 1) // 3 + 1}"
)

print(f"\n按月聚合完成，共 {len(monthly_df)} 个月")
print(f"月份范围: {monthly_df['月份'].iloc[0]} ~ {monthly_df['月份'].iloc[-1]}")

# ==================== 4. 处理紫金矿业和宁德时代 ====================
zj_df = pd.read_excel(file_path, sheet_name='紫金矿业', header=0)
nd_df = pd.read_excel(file_path, sheet_name='宁德时代', header=0)

zj_df['季度'] = zj_df['季度'].astype(str)
nd_df['季度'] = nd_df['季度'].astype(str)

zj_cols = ['净利润-同比增长', '净资产收益率', '净利率', '每股收益',
           '营业总收入-同比增长', '销售毛利率', '每股经营现金流量', '资产负债率']
nd_cols = zj_cols.copy()

zj_df_r = zj_df.rename(columns={c: f'紫金_{c}' for c in zj_cols})[['季度'] + [f'紫金_{c}' for c in zj_cols]]
nd_df_r = nd_df.rename(columns={c: f'宁德_{c}' for c in nd_cols})[['季度'] + [f'宁德_{c}' for c in nd_cols]]

# ==================== 5. 按月合并 ====================
merged = monthly_df.merge(zj_df_r, on='季度', how='inner')
merged = merged.merge(nd_df_r, on='季度', how='inner')

# 🔥 数据截止到2026年6月（2026Q3财报未发布）
merged = merged[merged['月份'] <= '2026-06'].reset_index(drop=True)

print(f"\n合并后数据: {len(merged)} 个月")
print(f"月份: {merged['月份'].tolist()}")


# ==================== 6. 生成标签 ====================
def get_month_label(month):
    m_data = df[df['月份'] == month].sort_values('日期').dropna(subset=[settle_col])
    if len(m_data) < 2:
        return np.nan
    first = m_data.iloc[0][settle_col]
    last = m_data.iloc[-1][settle_col]
    return 1 if last > first else 0


merged['标签'] = merged['月份'].apply(get_month_label)
merged = merged.dropna(subset=['标签'])
merged['标签'] = merged['标签'].astype(int)

print(f"\n标签生成完成: {len(merged)} 条")
print(f"标签分布: 空头(0)={sum(merged['标签'] == 0)}, 多头(1)={sum(merged['标签'] == 1)}")

print("\n各月标签详情:")
print(f"{'月份':<10} {'季度':<8} {'首日':>8} {'末日':>8} {'方向':<6}")
print("-" * 50)
for _, row in merged.iterrows():
    m = row['月份']
    m_data = df[df['月份'] == m].sort_values('日期').dropna(subset=[settle_col])
    first = m_data.iloc[0][settle_col]
    last = m_data.iloc[-1][settle_col]
    direction = "多头" if row['标签'] == 1 else "空头"
    print(f"{m:<10} {row['季度']:<8} {first:>8.0f} {last:>8.0f} {direction:<6}")

# ==================== 7. 定义全部特征列 ====================
supply_cols = [c for c in indicator_cols if c != settle_col]
all_feature_cols = supply_cols + [f'紫金_{c}' for c in zj_cols] + [f'宁德_{c}' for c in nd_cols]

print(f"\n全部特征数: {len(all_feature_cols)}")

# 填充缺失值
for col in all_feature_cols:
    if merged[col].isnull().any():
        merged[col] = merged[col].fillna(merged[col].mean())

# ==================== 8. 第一步：计算相关性 ====================
print("\n" + "=" * 90)
print("【第一步：计算所有特征与标签的相关系数】")
print("=" * 90)

correlations = {}
for col in all_feature_cols:
    r = merged[col].corr(merged['标签'])
    correlations[col] = r

corr_df = pd.DataFrame([
    {'特征': c, '相关系数': v, '绝对值': abs(v)}
    for c, v in correlations.items()
]).sort_values('绝对值', ascending=False).reset_index(drop=True)

print(f"\n{'排名':<4} {'特征':<55} {'相关系数':<12} {'方向'}")
print("-" * 90)
for i, (_, row) in enumerate(corr_df.iterrows(), 1):
    direction = "正相关" if row['相关系数'] > 0 else "负相关"
    marker = " 🔄" if ('需求' in row['特征'] or '出口量' in row['特征']) else ""
    print(f"{i:<4} {row['特征'][:54]:<55} {row['相关系数']:>8.3f}     {direction}{marker}")

# ==================== 9. 第二步：取Top 10因子 ====================
print("\n" + "=" * 90)
print("【第二步：取相关性绝对值 Top 10 因子】")
print("=" * 90)

top10_features = corr_df.head(10)['特征'].tolist()

print("\nTop 10 特征:")
for i, f in enumerate(top10_features, 1):
    r = correlations[f]
    direction = "正相关" if r > 0 else "负相关"
    print(f"  {i}. {f[:60]}")
    print(f"     相关系数: {r:.4f} ({direction})")

# ==================== 10. 第三步：只用Top 10做KNN ====================
print("\n" + "=" * 90)
print("【第三步：用 Top 10 因子做 KNN 留一法预测】")
print("=" * 90)

X = merged[top10_features].values
y = merged['标签'].values
months = merged['月份'].tolist()

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

loo = LeaveOneOut()
predictions, actuals, pred_months = [], [], []

for train_idx, test_idx in loo.split(X_scaled):
    X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
    y_tr, y_te = y[train_idx], y[test_idx]

    k = min(5, len(X_tr))
    knn = KNeighborsClassifier(n_neighbors=k)
    knn.fit(X_tr, y_tr)
    pred = knn.predict(X_te)[0]

    predictions.append(pred)
    actuals.append(y_te[0])
    pred_months.append(months[test_idx[0]])

correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
total = len(predictions)

print(f"\n{'月份':<10} {'预测':<6} {'实际':<6} {'结果'}")
print("-" * 40)
for m, p, a in zip(pred_months, predictions, actuals):
    p_dir = "多头" if p == 1 else "空头"
    a_dir = "多头" if a == 1 else "空头"
    result = "✅" if p == a else "❌"
    print(f"{m:<10} {p_dir:<6} {a_dir:<6} {result}")

print(f"\n准确率: {correct}/{total} = {correct / total:.2%}")
print(f"\n混淆矩阵:")
print(confusion_matrix(actuals, predictions))
print(f"\n分类报告:")
print(classification_report(actuals, predictions, target_names=['空头', '多头'], zero_division=0))

# ==================== 11. 对比：用全部特征的KNN ====================
print("\n" + "=" * 90)
print("【对比：用全部特征做 KNN】")
print("=" * 90)

X_all = merged[all_feature_cols].values
scaler_all = StandardScaler()
X_all_scaled = scaler_all.fit_transform(X_all)

predictions_all, actuals_all = [], []
for train_idx, test_idx in loo.split(X_all_scaled):
    X_tr, X_te = X_all_scaled[train_idx], X_all_scaled[test_idx]
    y_tr, y_te = y[train_idx], y[test_idx]

    k = min(5, len(X_tr))
    knn = KNeighborsClassifier(n_neighbors=k)
    knn.fit(X_tr, y_tr)
    pred = knn.predict(X_te)[0]

    predictions_all.append(pred)
    actuals_all.append(y_te[0])

correct_all = sum(1 for p, a in zip(predictions_all, actuals_all) if p == a)
total_all = len(predictions_all)

print(f"全部特征 ({len(all_feature_cols)}个) 准确率: {correct_all}/{total_all} = {correct_all / total_all:.2%}")
print(f"Top 10 特征准确率: {correct}/{total} = {correct / total:.2%}")

# ==================== 12. 可视化 ====================
try:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC']
    plt.rcParams['axes.unicode_minus'] = False

    # 图1: Top 20 特征相关性
    fig, ax = plt.subplots(figsize=(12, 10))
    top20 = corr_df.head(20)
    colors = ['green' if v > 0 else 'red' for v in top20['相关系数']]
    ax.barh(range(len(top20)), top20['相关系数'].values, color=colors)
    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels([c[:50] for c in top20['特征'].values])
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.axhline(y=9.5, color='blue', linestyle='--', linewidth=1.5, alpha=0.7)
    ax.text(0.02, 9.8, '↑ Top 10 分界线', fontsize=10, color='blue')
    ax.set_xlabel('与标签的相关系数')
    ax.set_title('Top 20 特征与碳酸锂期货月度涨跌的相关性')
    plt.tight_layout()
    plt.savefig('/Users/hanxin/Desktop/特征相关性_月度Top20.png', dpi=150, bbox_inches='tight')
    print("\n✅ 已保存: 特征相关性_月度Top20.png")
    plt.close('all')
except Exception as e:
    print(f"⚠️ 绘图失败: {e}")

# ==================== 13. 报告 ====================
print("\n" + "=" * 90)
print("【分析报告摘要】")
print("=" * 90)

print(f"""
一、数据概况
   月份数: {len(merged)} ({merged['月份'].iloc[0]} ~ {merged['月份'].iloc[-1]})
   覆盖季度: {sorted(merged['季度'].unique())}
   全部特征数: {len(all_feature_cols)}
   需求列已转正: {demand_col[0] if demand_col else 'N/A'}
   出口量列已转正: {export_col[0] if export_col else 'N/A'}

二、相关性 Top 10（进入KNN的因子）
""")
for i, f in enumerate(top10_features, 1):
    r = correlations[f]
    direction = "正相关" if r > 0 else "负相关"
    print(f"   {i}. {f[:55]}: {r:.4f} ({direction})")

print(f"""
三、KNN预测对比
   全部{len(all_feature_cols)}个特征: {correct_all}/{total_all} = {correct_all / total_all:.2%}
   Top 10 特征: {correct}/{total} = {correct / total:.2%}

四、Top 10 特征的预测详情
   空头正确: {sum(1 for p, a in zip(predictions, actuals) if a == 0 and p == 0)}/{sum(1 for a in actuals if a == 0)}
   多头正确: {sum(1 for p, a in zip(predictions, actuals) if a == 1 and p == 1)}/{sum(1 for a in actuals if a == 1)}
""")

print("=" * 90)
print("分析完成!")
print("=" * 90)