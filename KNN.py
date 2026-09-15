import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from datetime import datetime
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
print(f"价格数据: {price_df.shape[0]} 行, {price_df.shape[1]} 列")
print(f"供需平衡表: {balance_df.shape[0]} 行, {balance_df.shape[1]} 列")
print(f"紫金矿业: {zj_df.shape[0]} 行, {zj_df.shape[1]} 列")
print(f"宁德时代: {nd_df.shape[0]} 行, {nd_df.shape[1]} 列")


# ==================== 2. 数据预处理 ====================

def parse_quarter(date_str):
    """将日期转换为季度标签，如 '2026Q2'"""
    dt = pd.to_datetime(date_str)
    quarter_num = (dt.month - 1) // 3 + 1
    return f"{dt.year}Q{quarter_num}"


# 2.1 处理价格数据
price_columns = [
    'SMM: 锂辉石精矿（CIF中国）指数 - 平均价: 日度',
    'SMM: 电池级碳酸锂 - 平均价: 日度',
    'SMM: 工业级碳酸锂 - 平均价: 日度',
    'SMM: 碳酸锂主力合约 - 结算价: 日度',  # 这个作为标签，不用于特征
    'SMM: 碳酸锂主力合约仓单 - 日度',
    'SMM: 碳酸锂期现基差 - 日度'
]

# 重命名列方便操作
price_df.columns = ['日期'] + price_columns

# 删除空行
price_df = price_df.dropna(subset=['日期'])
price_df['日期'] = pd.to_datetime(price_df['日期'])
price_df['季度'] = price_df['日期'].apply(parse_quarter)

# 只保留有完整数据的季度（与紫金矿业、宁德时代匹配）
price_df['year'] = price_df['日期'].dt.year
price_df['month'] = price_df['日期'].dt.month

# 计算每个季度的平均值
price_quarterly = price_df.groupby('季度').agg({
    'SMM: 锂辉石精矿（CIF中国）指数 - 平均价: 日度': 'mean',
    'SMM: 电池级碳酸锂 - 平均价: 日度': 'mean',
    'SMM: 工业级碳酸锂 - 平均价: 日度': 'mean',
    'SMM: 碳酸锂主力合约 - 结算价: 日度': 'mean',  # 用于计算标签
    'SMM: 碳酸锂主力合约仓单 - 日度': 'mean',
    'SMM: 碳酸锂期现基差 - 日度': 'mean'
}).reset_index()

print("\n价格数据季度聚合完成:")
print(price_quarterly)

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

# 对每个季度，对每个指标取有效值的平均
balance_quarterly = balance_df.groupby('季度').agg({
    col: lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
    for col in balance_columns
}).reset_index()

print("\n供需平衡表季度聚合完成:")
print(balance_quarterly)

# 2.3 合并紫金矿业和宁德时代数据
# 标准化季度格式（确保与上面一致）
zj_df['季度'] = zj_df['季度'].astype(str)
nd_df['季度'] = nd_df['季度'].astype(str)

# 紫金矿业的列
zj_columns = [
    '净利润-同比增长', '净资产收益率', '净利率', '每股收益',
    '营业总收入-同比增长', '销售毛利率', '每股经营现金流量', '资产负债率'
]
zj_renamed = {col: f'紫金_{col}' for col in zj_columns}
zj_df_renamed = zj_df.rename(columns=zj_renamed)

# 宁德时代的列
nd_columns = [
    '净利润-同比增长', '净资产收益率', '净利率', '每股收益',
    '营业总收入-同比增长', '销售毛利率', '每股经营现金流量', '资产负债率'
]
nd_renamed = {col: f'宁德_{col}' for col in nd_columns}
nd_df_renamed = nd_df.rename(columns=nd_renamed)

# ==================== 3. 合并所有数据 ====================

# 从价格数据中获取季度标签
quarter_labels = price_quarterly['季度'].unique()
print(f"\n所有季度: {sorted(quarter_labels)}")

# 逐步合并
merged_df = price_quarterly.copy()
merged_df = merged_df.merge(balance_quarterly, on='季度', how='inner')
merged_df = merged_df.merge(zj_df_renamed, on='季度', how='inner')
merged_df = merged_df.merge(nd_df_renamed, on='季度', how='inner')

print(f"\n合并后数据条数: {len(merged_df)}")
print(f"列数: {len(merged_df.columns)}")


# ==================== 4. 生成标签 ====================

def generate_labels(df):
    """根据季度首日和末日结算价生成标签"""
    labels = []
    for quarter in df['季度'].unique():
        # 获取该季度的所有数据
        quarter_data = price_df[price_df['季度'] == quarter]
        if len(quarter_data) == 0:
            labels.append(np.nan)
            continue

        # 按日期排序
        quarter_data = quarter_data.sort_values('日期')
        first_price = quarter_data.iloc[0]['SMM: 碳酸锂主力合约 - 结算价: 日度']
        last_price = quarter_data.iloc[-1]['SMM: 碳酸锂主力合约 - 结算价: 日度']

        # 多头：首日 < 末日，空头：首日 > 末日
        if first_price < last_price:
            labels.append(1)  # 多头
        elif first_price > last_price:
            labels.append(0)  # 空头
        else:
            labels.append(0)  # 持平视为空头

    return labels


# 为每个季度生成标签
quarter_list = merged_df['季度'].tolist()
label_dict = {}
for q in quarter_list:
    q_data = price_df[price_df['季度'] == q]
    q_data = q_data.sort_values('日期')
    if len(q_data) > 1:
        first = q_data.iloc[0]['SMM: 碳酸锂主力合约 - 结算价: 日度']
        last = q_data.iloc[-1]['SMM: 碳酸锂主力合约 - 结算价: 日度']
        label_dict[q] = 1 if first < last else 0
    else:
        label_dict[q] = 0

merged_df['标签'] = merged_df['季度'].map(label_dict)

print(f"\n标签生成完成，共有 {len(merged_df)} 条数据")
print("标签分布:")
print(merged_df['标签'].value_counts().to_string())

# ==================== 5. 准备特征和标签 ====================

# 定义特征列（排除日期、季度、结算价、标签）
feature_columns = [
    # 价格特征 (4个，排除结算价)
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
    # 紫金矿业特征 (8个)
    '紫金_净利润-同比增长',
    '紫金_净资产收益率',
    '紫金_净利率',
    '紫金_每股收益',
    '紫金_营业总收入-同比增长',
    '紫金_销售毛利率',
    '紫金_每股经营现金流量',
    '紫金_资产负债率',
    # 宁德时代特征 (8个)
    '宁德_净利润-同比增长',
    '宁德_净资产收益率',
    '宁德_净利率',
    '宁德_每股收益',
    '宁德_营业总收入-同比增长',
    '宁德_销售毛利率',
    '宁德_每股经营现金流量',
    '宁德_资产负债率'
]

# 检查是否有缺失值
print("\n检查缺失值:")
print(merged_df[feature_columns].isnull().sum().to_string())

# 填充缺失值（用均值填充）
for col in feature_columns:
    if merged_df[col].isnull().any():
        mean_val = merged_df[col].mean()
        merged_df[col] = merged_df[col].fillna(mean_val)
        print(f"列 {col} 用均值 {mean_val:.2f} 填充")

# ==================== 6. KNN模型训练和预测 ====================

# 按季度排序
merged_df = merged_df.sort_values('季度')

# 获取特征和标签
X = merged_df[feature_columns].values
y = merged_df['标签'].values

# 标准化特征
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 获取最近两个季度的数据作为测试集
if len(merged_df) >= 2:
    # 取最近两个季度的数据平均作为测试样本
    test_indices = [-2, -1]
    test_X = X_scaled[test_indices].mean(axis=0).reshape(1, -1)
    test_quarters = merged_df['季度'].iloc[test_indices].tolist()
    print(f"\n测试数据来自最近两个季度: {test_quarters}")
else:
    # 如果数据不足，用最后一个季度
    test_X = X_scaled[-1:].reshape(1, -1)
    print(f"\n测试数据来自最后一个季度: {merged_df['季度'].iloc[-1]}")

# 训练数据 (排除测试数据所用的季度)
train_indices = [i for i in range(len(merged_df)) if i not in test_indices]
X_train = X_scaled[train_indices]
y_train = y[train_indices]

print(f"训练样本数: {len(X_train)}")
print(f"测试样本数: {len(test_X)}")

# 创建KNN分类器 (k=5)
knn = KNeighborsClassifier(n_neighbors=5)
knn.fit(X_train, y_train)

# 预测
prediction = knn.predict(test_X)
prediction_proba = knn.predict_proba(test_X)

print("\n" + "=" * 60)
print("KNN预测结果")
print("=" * 60)
print(f"预测标签: {'多头' if prediction[0] == 1 else '空头'}")
print(f"预测概率: 空头={prediction_proba[0][0]:.2%}, 多头={prediction_proba[0][1]:.2%}")

# 显示最近5个邻居
distances, indices = knn.kneighbors(test_X)
print(f"\n最近的{len(indices[0])}个邻居索引: {indices[0]}")
print(f"对应的季度: {[merged_df['季度'].iloc[i] for i in indices[0]]}")
print(f"对应的标签: {[y[i] for i in indices[0]]}")

# ==================== 7. 模型评估 ====================

# 由于数据量太少，使用留一法交叉验证评估
from sklearn.model_selection import LeaveOneOut

loo = LeaveOneOut()
correct = 0
total = 0

loo_predictions = []
loo_actual = []

for train_idx, test_idx in loo.split(X_scaled):
    X_train_loo, X_test_loo = X_scaled[train_idx], X_scaled[test_idx]
    y_train_loo, y_test_loo = y[train_idx], y[test_idx]

    knn_loo = KNeighborsClassifier(n_neighbors=5)
    knn_loo.fit(X_train_loo, y_train_loo)

    pred = knn_loo.predict(X_test_loo)
    loo_predictions.append(pred[0])
    loo_actual.append(y_test_loo[0])

    if pred[0] == y_test_loo[0]:
        correct += 1
    total += 1

print("\n" + "=" * 60)
print("留一法交叉验证评估")
print("=" * 60)
print(f"准确率: {correct}/{total} = {correct / total:.2%}")

# 混淆矩阵
from sklearn.metrics import confusion_matrix, classification_report

print("\n混淆矩阵:")
cm = confusion_matrix(loo_actual, loo_predictions)
print(cm)
print("\n分类报告:")
print(classification_report(loo_actual, loo_predictions, target_names=['空头', '多头']))

# ==================== 8. 数据汇总展示 ====================

print("\n" + "=" * 60)
print("季度数据汇总")
print("=" * 60)

summary = merged_df[['季度', '标签'] + feature_columns[:5]].copy()
summary['标签_文本'] = summary['标签'].map({0: '空头', 1: '多头'})
print(summary[['季度', '标签_文本', feature_columns[0], feature_columns[1], feature_columns[2], feature_columns[3],
               feature_columns[4]]].to_string())

print("\n" + "=" * 60)
print("预测完成!")
print(
    f"基于最近两个季度 ({', '.join(test_quarters)}) 的平均数据预测下个季度为: {'多头' if prediction[0] == 1 else '空头'}")
print("=" * 60)