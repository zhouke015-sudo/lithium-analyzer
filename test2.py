import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, classification_report
import warnings

warnings.filterwarnings('ignore')

# ==================== 1. 数据加载 ====================
file_path = 'SMM_碳酸锂日度.xlsx'

# 读取价格数据 (Sheet 1)
price_df = pd.read_excel(file_path, sheet_name='价格数据', header=7)

# 读取供需平衡表 (Sheet 2)
balance_df = pd.read_excel(file_path, sheet_name='供需平衡表', header=7)

# 读取紫金矿业 (Sheet 3)
zj_df = pd.read_excel(file_path, sheet_name='紫金矿业', header=0)

# 读取宁德时代 (Sheet 4)
nd_df = pd.read_excel(file_path, sheet_name='宁德时代', header=0)

print("=" * 60)
print("数据加载完成")
print("=" * 60)


# ==================== 2. 数据预处理 ====================

def parse_quarter(date_str):
    dt = pd.to_datetime(date_str)
    quarter_num = (dt.month - 1) // 3 + 1
    return f"{dt.year}Q{quarter_num}"


# 2.1 处理价格数据
price_columns = [
    'SMM: 锂辉石精矿（CIF中国）指数 - 平均价: 日度',
    'SMM: 电池级碳酸锂 - 平均价: 日度',
    'SMM: 工业级碳酸锂 - 平均价: 日度',
    'SMM: 碳酸锂主力合约 - 结算价: 日度',
    'SMM: 碳酸锂主力合约仓单 - 日度',
    'SMM: 碳酸锂期现基差 - 日度'
]

price_df.columns = ['日期'] + price_columns
price_df = price_df.dropna(subset=['日期'])
price_df['日期'] = pd.to_datetime(price_df['日期'])
price_df['季度'] = price_df['日期'].apply(parse_quarter)

# 按季度聚合价格数据（排除结算价）
price_quarterly = price_df.groupby('季度').agg({
    'SMM: 锂辉石精矿（CIF中国）指数 - 平均价: 日度': 'mean',
    'SMM: 电池级碳酸锂 - 平均价: 日度': 'mean',
    'SMM: 工业级碳酸锂 - 平均价: 日度': 'mean',
    'SMM: 碳酸锂主力合约仓单 - 日度': 'mean',
    'SMM: 碳酸锂期现基差 - 日度': 'mean'
}).reset_index()

print("\n价格数据季度聚合完成:")
print(f"共 {len(price_quarterly)} 个季度")

# 2.2 处理供需平衡表
balance_columns = [
    'SMM: 碳酸锂供需平衡: 产量: 月度',
    'SMM: 碳酸锂供需平衡: 需求: 月度',
    'SMM: 碳酸锂供需平衡: 进口量: 月度',
    'SMM: 碳酸锂供需平衡: 出口量: 月度',
    'SMM: 碳酸锂供需平衡: 平衡值: 月度',
    'SMM: 碳酸锂供需平衡: 累计平衡值: 月度',
    'SMM: 盐湖冶炼碳酸锂产能: 月度',
    'SMM: 锂云母冶炼碳酸锂产能: 月度',
    'SMM: 锂辉石冶炼碳酸锂产能: 月度',
    'SMM: 碳酸锂月度冶炼总产能: 月度',
    'SMM: 碳酸锂开工率: 盐湖: 月度',
    'SMM: 碳酸锂开工率: 锂云母: 月度',
    'SMM: 碳酸锂开工率: 锂辉石: 月度'
]

balance_df.columns = ['日期'] + balance_columns
balance_df = balance_df.dropna(subset=['日期'])
balance_df['日期'] = pd.to_datetime(balance_df['日期'])
balance_df['季度'] = balance_df['日期'].apply(parse_quarter)

# 按季度聚合（对有效值取平均）
balance_quarterly = balance_df.groupby('季度').agg({
    col: lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
    for col in balance_columns
}).reset_index()

print(f"\n供需平衡表季度聚合完成，共 {len(balance_quarterly)} 个季度")

# 2.3 处理紫金矿业和宁德时代
zj_df['季度'] = zj_df['季度'].astype(str)
nd_df['季度'] = nd_df['季度'].astype(str)

zj_columns = ['净利润-同比增长', '净资产收益率', '净利率', '每股收益',
              '营业总收入-同比增长', '销售毛利率', '每股经营现金流量', '资产负债率']
zj_renamed = {col: f'紫金_{col}' for col in zj_columns}
zj_df_renamed = zj_df.rename(columns=zj_renamed)

nd_renamed = {col: f'宁德_{col}' for col in zj_columns}
nd_df_renamed = nd_df.rename(columns=nd_renamed)

print(f"\n紫金矿业: {len(zj_df)} 个季度")
print(f"宁德时代: {len(nd_df)} 个季度")

# ==================== 3. 合并所有数据 ====================

merged_df = price_quarterly.copy()
merged_df = merged_df.merge(balance_quarterly, on='季度', how='inner')
merged_df = merged_df.merge(zj_df_renamed, on='季度', how='inner')
merged_df = merged_df.merge(nd_df_renamed, on='季度', how='inner')

print(f"\n合并后数据条数: {len(merged_df)}")
print(f"可用季度: {merged_df['季度'].tolist()}")


# ==================== 4. 生成标签（季度首日 vs 末日结算价）====================

def get_quarter_label(quarter):
    """根据季度首日和末日结算价生成标签"""
    q_data = price_df[price_df['季度'] == quarter].sort_values('日期')
    if len(q_data) < 2:
        return np.nan
    first = q_data.iloc[0]['SMM: 碳酸锂主力合约 - 结算价: 日度']
    last = q_data.iloc[-1]['SMM: 碳酸锂主力合约 - 结算价: 日度']
    return 1 if last > first else 0


merged_df['标签'] = merged_df['季度'].apply(get_quarter_label)
merged_df = merged_df.dropna(subset=['标签'])
merged_df['标签'] = merged_df['标签'].astype(int)

print(f"\n标签生成完成，共 {len(merged_df)} 条数据")
print("标签分布:")
print(merged_df['标签'].value_counts().to_string())

# 显示每个季度的标签详情
print("\n各季度标签详情:")
for _, row in merged_df.iterrows():
    q = row['季度']
    direction = "多头" if row['标签'] == 1 else "空头"
    # 获取首末日价格
    q_data = price_df[price_df['季度'] == q].sort_values('日期')
    first = q_data.iloc[0]['SMM: 碳酸锂主力合约 - 结算价: 日度']
    last = q_data.iloc[-1]['SMM: 碳酸锂主力合约 - 结算价: 日度']
    print(f"  {q}: 首日={first:.0f} -> 末日={last:.0f}, {direction}")

# ==================== 5. 准备特征 ====================

feature_columns = [
    # 价格特征 (5个)
    'SMM: 锂辉石精矿（CIF中国）指数 - 平均价: 日度',
    'SMM: 电池级碳酸锂 - 平均价: 日度',
    'SMM: 工业级碳酸锂 - 平均价: 日度',
    'SMM: 碳酸锂主力合约仓单 - 日度',
    'SMM: 碳酸锂期现基差 - 日度',
    # 供需平衡特征 (13个)
    'SMM: 碳酸锂供需平衡: 产量: 月度',
    'SMM: 碳酸锂供需平衡: 需求: 月度',
    'SMM: 碳酸锂供需平衡: 进口量: 月度',
    'SMM: 碳酸锂供需平衡: 出口量: 月度',
    'SMM: 碳酸锂供需平衡: 平衡值: 月度',
    'SMM: 碳酸锂供需平衡: 累计平衡值: 月度',
    'SMM: 盐湖冶炼碳酸锂产能: 月度',
    'SMM: 锂云母冶炼碳酸锂产能: 月度',
    'SMM: 锂辉石冶炼碳酸锂产能: 月度',
    'SMM: 碳酸锂月度冶炼总产能: 月度',
    'SMM: 碳酸锂开工率: 盐湖: 月度',
    'SMM: 碳酸锂开工率: 锂云母: 月度',
    'SMM: 碳酸锂开工率: 锂辉石: 月度',
    # 紫金矿业 (8个)
    '紫金_净利润-同比增长',
    '紫金_净资产收益率',
    '紫金_净利率',
    '紫金_每股收益',
    '紫金_营业总收入-同比增长',
    '紫金_销售毛利率',
    '紫金_每股经营现金流量',
    '紫金_资产负债率',
    # 宁德时代 (8个)
    '宁德_净利润-同比增长',
    '宁德_净资产收益率',
    '宁德_净利率',
    '宁德_每股收益',
    '宁德_营业总收入-同比增长',
    '宁德_销售毛利率',
    '宁德_每股经营现金流量',
    '宁德_资产负债率'
]

# 填充缺失值
for col in feature_columns:
    if merged_df[col].isnull().any():
        mean_val = merged_df[col].mean()
        merged_df[col] = merged_df[col].fillna(mean_val)

# ==================== 6. 留一法（Leave-One-Out）预测 ====================

# 按季度排序
merged_df = merged_df.sort_values('季度').reset_index(drop=True)

X = merged_df[feature_columns].values
y = merged_df['标签'].values
quarters = merged_df['季度'].tolist()

# 标准化
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print("\n" + "=" * 60)
print("留一法预测（每个季度依次作为测试集，其余10个作为训练集）")
print("=" * 60)
print(f"总样本数: {len(merged_df)} 个季度")
print(f"预测方式: 每个季度用另外 {len(merged_df) - 1} 个季度训练，预测当前季度")
print(f"邻居数 k = 5")

# 留一法预测
predictions = []
actuals = []
pred_quarters = []
pred_probas = []
neighbor_info = []

for test_idx in range(len(merged_df)):
    # 训练集：除了当前季度之外的所有季度
    train_indices = [i for i in range(len(merged_df)) if i != test_idx]
    X_train = X_scaled[train_indices]
    y_train = y[train_indices]

    # 测试集：当前季度
    X_test = X_scaled[test_idx].reshape(1, -1)
    y_test = y[test_idx]
    current_quarter = quarters[test_idx]

    # 训练KNN
    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(X_train, y_train)

    # 预测
    pred = knn.predict(X_test)[0]
    pred_proba = knn.predict_proba(X_test)

    predictions.append(pred)
    actuals.append(y_test)
    pred_quarters.append(current_quarter)
    pred_probas.append(pred_proba[0])

    # 获取邻居信息
    distances, indices = knn.kneighbors(X_test)
    neighbor_quarters = [quarters[i] for i in indices[0]]
    neighbor_labels = [y[i] for i in indices[0]]
    neighbor_info.append((neighbor_quarters, neighbor_labels))

# ==================== 7. 统计胜率 ====================

print("\n" + "=" * 60)
print("预测结果详情")
print("=" * 60)

correct = 0
total = len(predictions)

print(f"\n{'季度':<10} {'预测':<6} {'实际':<6} {'结果':<6} {'概率(多头)':<12} {'邻居季度'}")
print("-" * 80)

for i, (q, p, a, proba, (nq, nl)) in enumerate(zip(pred_quarters, predictions, actuals, pred_probas, neighbor_info)):
    p_dir = "多头" if p == 1 else "空头"
    a_dir = "多头" if a == 1 else "空头"
    result = "✅" if p == a else "❌"
    if p == a:
        correct += 1

    neighbor_str = ", ".join(nq[:3]) + ("..." if len(nq) > 3 else "")
    print(f"{q:<10} {p_dir:<6} {a_dir:<6} {result:<6} {proba[1]:<11.1%} {neighbor_str}")

# 总体胜率
print("\n" + "=" * 60)
print("最终统计")
print("=" * 60)
print(f"总预测次数: {total}")
print(f"正确次数: {correct}")
print(f"错误次数: {total - correct}")
print(f"胜率: {correct}/{total} = {correct / total:.2%}")

# 混淆矩阵
print("\n混淆矩阵:")
cm = confusion_matrix(actuals, predictions)
print(cm)
print("\n分类报告:")
print(classification_report(actuals, predictions, target_names=['空头', '多头']))

# 分年份统计
print("\n分年份统计:")
years = {}
for q, p, a in zip(pred_quarters, predictions, actuals):
    year = q[:4]
    if year not in years:
        years[year] = {'correct': 0, 'total': 0, 'details': []}
    years[year]['total'] += 1
    if p == a:
        years[year]['correct'] += 1
    years[year]['details'].append((q, p, a))

for year, stats in sorted(years.items()):
    rate = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
    details = ", ".join([f"{q}({'✅' if p == a else '❌'})" for q, p, a in stats['details']])
    print(f"  {year}: {stats['correct']}/{stats['total']} = {rate:.2%}  [{details}]")

# 总结
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print(f"在 {total} 个季度的留一法测试中，KNN(k=5) 预测对了 {correct} 个季度")
print(f"整体胜率为 {correct / total:.2%}")

# 显示预测错误的季度
wrong_quarters = [q for q, p, a in zip(pred_quarters, predictions, actuals) if p != a]
if wrong_quarters:
    print(f"\n预测错误的季度: {', '.join(wrong_quarters)}")
else:
    print("\n所有季度预测正确！🎉")

print("\n" + "=" * 60)
print("分析完成!")
print("=" * 60)