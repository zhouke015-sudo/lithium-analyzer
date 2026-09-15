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
file_path = '/Users/hanxin/Desktop/碳酸锂船运数据.xlsx'

df = pd.read_excel(file_path, sheet_name='Sheet1', header=3)
df.columns = ['日期', '黑德兰港发往中国', '全球发运至中国', '全球发运量', '结算价']

print("=" * 80)
print("原始数据加载完成")
print("=" * 80)
print(f"总行数: {len(df)}")
print(f"列名: {list(df.columns)}")

# 转换日期
df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
df = df.dropna(subset=['日期'])
df = df.sort_values('日期').reset_index(drop=True)

# 转换数值列
for col in ['黑德兰港发往中国', '全球发运至中国', '全球发运量', '结算价']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 添加月份列
df['月份'] = df['日期'].dt.to_period('M')

print(f"\n有效数据日期范围: {df['日期'].min()} ~ {df['日期'].max()}")

# 检查每列的有效数据
print("\n各列有效数据统计:")
for col in ['黑德兰港发往中国', '全球发运至中国', '全球发运量', '结算价']:
    valid = df[col].dropna()
    if len(valid) > 0:
        valid_dates = df.loc[valid.index, '日期']
        print(f"  {col}: {len(valid)} 条, "
              f"范围 {valid_dates.min().strftime('%Y-%m')} ~ {valid_dates.max().strftime('%Y-%m')}")
    else:
        print(f"  {col}: 无有效数据")

# ==================== 2. 按月聚合 ====================

# 按月聚合，取平均值
monthly_df = df.groupby('月份').agg({
    '黑德兰港发往中国': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan,
    '全球发运至中国': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan,
    '全球发运量': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan,
    '结算价': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
}).reset_index()

monthly_df['月份_str'] = monthly_df['月份'].astype(str)
monthly_df = monthly_df.sort_values('月份').reset_index(drop=True)

print("\n" + "=" * 80)
print("按月聚合完成")
print("=" * 80)
print(f"总月份数: {len(monthly_df)}")

# 检查每个指标的月度覆盖情况
print("\n各指标月度覆盖:")
for col in ['黑德兰港发往中国', '全球发运至中国', '全球发运量', '结算价']:
    valid_months = monthly_df[monthly_df[col].notna()]['月份_str'].tolist()
    if len(valid_months) > 0:
        print(f"  {col}: {len(valid_months)} 个月 "
              f"({valid_months[0]} ~ {valid_months[-1]})")
    else:
        print(f"  {col}: 无有效数据")


# ==================== 3. 生成标签 ====================

# 标签：当月结算价 vs 下月结算价的涨跌
# 但这里要分析的是"船运信息与结算价的关系"，所以用当月首日vs末日结算价
# 先看原始日度数据，计算每个月结算价的变化方向

def get_monthly_label(year_month):
    """根据当月首日和末日结算价生成标签"""
    month_data = df[df['月份'] == year_month].sort_values('日期')
    month_data = month_data.dropna(subset=['结算价'])
    if len(month_data) < 2:
        return np.nan
    first = month_data.iloc[0]['结算价']
    last = month_data.iloc[-1]['结算价']
    return 1 if last > first else 0


monthly_df['标签'] = monthly_df['月份'].apply(get_monthly_label)
monthly_df = monthly_df.dropna(subset=['标签'])
monthly_df['标签'] = monthly_df['标签'].astype(int)

print(f"\n标签生成完成: {len(monthly_df)} 个月")
print("标签分布:")
print(monthly_df['标签'].value_counts().to_string())

# ==================== 4. 三个指标分别与结算价做相关性分析 ====================

print("\n" + "=" * 80)
print("【相关性分析】船运指标 vs 碳酸锂结算价")
print("=" * 80)

# 定义三个指标
indicators = {
    '黑德兰港发往中国': 'SMM: 锂矿航运: 澳洲黑德兰港锂辉石精矿出港: 发往中国: 月度',
    '全球发运至中国': 'SMM: 锂矿航运: 全球锂辉石发运至中国量: 总计: 周度',
    '全球发运量': 'SMM: 锂矿航运: 全球锂辉石发运量: 总计: 周度'
}

correlation_results = {}

for col, full_name in indicators.items():
    # 找出该指标和结算价都有数据的月份
    valid_data = monthly_df.dropna(subset=[col, '结算价'])

    print(f"\n{'=' * 80}")
    print(f"指标: {full_name}")
    print(f"{'=' * 80}")

    if len(valid_data) < 3:
        print(f"  ⚠️ 有效数据不足 ({len(valid_data)} 个月)，跳过")
        correlation_results[col] = {
            'n': len(valid_data),
            'pearson': np.nan,
            'status': '数据不足'
        }
        continue

    print(f"  有效月份数: {len(valid_data)}")
    print(f"  时间范围: {valid_data['月份_str'].iloc[0]} ~ {valid_data['月份_str'].iloc[-1]}")

    # 计算皮尔逊相关系数
    pearson_corr = valid_data[col].corr(valid_data['结算价'])

    # 计算斯皮尔曼相关系数（秩相关，对非线性关系更稳健）
    spearman_corr = valid_data[col].corr(valid_data['结算价'], method='spearman')

    # 计算与标签的相关系数（点二列相关）
    label_corr = valid_data[col].corr(valid_data['标签'])

    print(f"\n  皮尔逊相关系数 (vs 结算价): {pearson_corr:.4f}")
    print(f"  斯皮尔曼相关系数 (vs 结算价): {spearman_corr:.4f}")
    print(f"  点二列相关 (vs 涨跌标签): {label_corr:.4f}")


    # 解读
    def interpret_corr(r):
        abs_r = abs(r)
        if abs_r >= 0.7:
            strength = "强"
        elif abs_r >= 0.4:
            strength = "中等"
        elif abs_r >= 0.2:
            strength = "弱"
        else:
            strength = "极弱/无"
        direction = "正相关" if r > 0 else "负相关"
        return f"{strength}{direction}"


    print(f"\n  解读: 船运量与结算价呈【{interpret_corr(pearson_corr)}】")

    # 业务解读
    print(f"\n  业务解读:")
    if pearson_corr > 0.3:
        print(f"    → 船运量增加时，碳酸锂价格上涨")
        print(f"    → 可能反映：下游需求旺盛，锂矿采购积极，推动价格上行")
    elif pearson_corr < -0.3:
        print(f"    → 船运量增加时，碳酸锂价格下跌")
        print(f"    → 可能反映：大量锂矿到港，供给增加预期压制价格")
    else:
        print(f"    → 船运量与价格关系不明显，需结合其他因素分析")

    # 显示详细数据
    print(f"\n  详细数据:")
    print(f"  {'月份':<10} {'船运量':>12} {'结算价':>10} {'标签':>6}")
    print(f"  {'-' * 42}")
    for _, row in valid_data.iterrows():
        label_str = "多头" if row['标签'] == 1 else "空头"
        print(f"  {row['月份_str']:<10} {row[col]:>12.0f} {row['结算价']:>10.0f} {label_str:>6}")

    correlation_results[col] = {
        'n': len(valid_data),
        'pearson': pearson_corr,
        'spearman': spearman_corr,
        'label_corr': label_corr,
        'valid_data': valid_data
    }

# ==================== 5. 汇总对比 ====================

print("\n" + "=" * 80)
print("【汇总对比】三个船运指标与结算价的相关性")
print("=" * 80)

summary_data = []
for col, name in indicators.items():
    if col in correlation_results and not np.isnan(correlation_results[col].get('pearson', np.nan)):
        r = correlation_results[col]
        summary_data.append({
            '指标': name,
            '有效月份': r['n'],
            '皮尔逊相关': r['pearson'],
            '斯皮尔曼相关': r['spearman'],
            '与标签相关': r['label_corr']
        })

if summary_data:
    summary_df = pd.DataFrame(summary_data)
    summary_df = summary_df.sort_values('皮尔逊相关', key=abs, ascending=False)
    print(summary_df.to_string(index=False))

# ==================== 6. KNN分析 ====================

print("\n" + "=" * 80)
print("【KNN分析】用船运数据预测价格涨跌")
print("=" * 80)

# 对每个指标，单独用KNN分析
for col, full_name in indicators.items():
    print(f"\n{'=' * 80}")
    print(f"KNN分析: {full_name}")
    print(f"{'=' * 80}")

    valid_data = monthly_df.dropna(subset=[col, '标签']).copy()

    if len(valid_data) < 6:
        print(f"  ⚠️ 数据不足 ({len(valid_data)} 个月)，至少需要6个月")
        continue

    print(f"  有效月份数: {len(valid_data)}")

    # 特征和标签
    X = valid_data[[col]].values
    y = valid_data['标签'].values

    # 标准化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 留一法交叉验证
    loo = LeaveOneOut()
    predictions = []
    actuals = []

    for train_idx, test_idx in loo.split(X_scaled):
        X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # KNN (k=min(5, 训练样本数))
        k = min(5, len(X_train))
        knn = KNeighborsClassifier(n_neighbors=k)
        knn.fit(X_train, y_train)

        pred = knn.predict(X_test)[0]
        predictions.append(pred)
        actuals.append(y_test[0])

    # 计算准确率
    correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
    total = len(predictions)
    accuracy = correct / total if total > 0 else 0

    print(f"\n  留一法KNN预测结果:")
    print(f"    准确率: {correct}/{total} = {accuracy:.2%}")

    # 混淆矩阵
    if len(set(actuals)) > 1:
        print(f"\n  混淆矩阵:")
        print(confusion_matrix(actuals, predictions))
        print(f"\n  分类报告:")
        print(classification_report(actuals, predictions,
                                    target_names=['空头', '多头'],
                                    zero_division=0))

    # 显示详细预测结果
    print(f"\n  详细预测:")
    print(f"  {'月份':<10} {'船运量':>12} {'预测':>6} {'实际':>6} {'结果':>4}")
    print(f"  {'-' * 44}")
    for i, (_, row) in enumerate(valid_data.iterrows()):
        pred_str = "多头" if predictions[i] == 1 else "空头"
        actual_str = "多头" if actuals[i] == 1 else "空头"
        result = "✅" if predictions[i] == actuals[i] else "❌"
        print(f"  {row['月份_str']:<10} {row[col]:>12.0f} {pred_str:>6} {actual_str:>6} {result:>4}")

# ==================== 7. 可视化 ====================

print("\n" + "=" * 80)
print("【可视化】")
print("=" * 80)

try:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC']
    plt.rcParams['axes.unicode_minus'] = False

    # 图1: 三个指标与结算价的时间序列对比
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    for i, (col, name) in enumerate(indicators.items()):
        valid_data = monthly_df.dropna(subset=[col, '结算价'])
        if len(valid_data) == 0:
            continue

        ax1 = axes[i]
        ax2 = ax1.twinx()

        x = range(len(valid_data))
        ax1.bar(x, valid_data[col], alpha=0.6, color='steelblue', label='船运量')
        ax2.plot(x, valid_data['结算价'], color='red', marker='o',
                 linewidth=2, markersize=4, label='结算价')

        ax1.set_xlabel('月份')
        ax1.set_ylabel('船运量 (吨)', color='steelblue')
        ax2.set_ylabel('结算价 (元/吨)', color='red')
        ax1.set_title(f'{name} vs 碳酸锂结算价', fontsize=12)

        # 设置x轴标签
        step = max(1, len(valid_data) // 10)
        ax1.set_xticks(list(x)[::step])
        ax1.set_xticklabels(valid_data['月份_str'].tolist()[::step],
                            rotation=45, ha='right')

        # 图例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    plt.savefig('/Users/hanxin/Desktop/船运数据_vs_结算价.png', dpi=150, bbox_inches='tight')
    print("✅ 已保存: 船运数据_vs_结算价.png")

    # 图2: 散点图
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for i, (col, name) in enumerate(indicators.items()):
        valid_data = monthly_df.dropna(subset=[col, '结算价'])
        if len(valid_data) == 0:
            continue

        ax = axes[i]
        colors = ['green' if l == 1 else 'red' for l in valid_data['标签']]
        ax.scatter(valid_data[col], valid_data['结算价'], c=colors, alpha=0.6, s=50)

        # 添加趋势线
        z = np.polyfit(valid_data[col], valid_data['结算价'], 1)
        p = np.poly1d(z)
        x_sorted = np.sort(valid_data[col])
        ax.plot(x_sorted, p(x_sorted), 'b--', alpha=0.5, linewidth=1)

        # 计算相关系数
        r = valid_data[col].corr(valid_data['结算价'])
        ax.set_xlabel('船运量 (吨)')
        ax.set_ylabel('结算价 (元/吨)')
        ax.set_title(f'{name}\nr = {r:.3f}', fontsize=10)

        # 图例
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor='green', alpha=0.6, label='多头'),
            Patch(facecolor='red', alpha=0.6, label='空头')
        ]
        ax.legend(handles=legend_elements, loc='best')

    plt.tight_layout()
    plt.savefig('/Users/hanxin/Desktop/船运数据_散点图.png', dpi=150, bbox_inches='tight')
    print("✅ 已保存: 船运数据_散点图.png")

    plt.close('all')

except Exception as e:
    print(f"⚠️ 绘图失败: {e}")

# ==================== 8. 生成分析报告 ====================

print("\n" + "=" * 80)
print("【分析报告】")
print("=" * 80)

print("""
┌──────────────────────────────────────────────────────────────────────────────┐
│                    碳酸锂船运数据与期货价格关系分析报告                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  一、数据说明                                                                 │
│  ─────────────────────────────────────────────────────────────────────────    │
│  数据来源: SMM锂矿航运数据 + GFEX碳酸锂主力合约结算价                          │
│  时间范围: 2023-07 ~ 2026-09                                                 │
│  聚合方式: 按月取平均值                                                       │
│                                                                              │
│  三个船运指标:                                                                │
│    1. 澳洲黑德兰港锂辉石精矿出港发往中国 (月度, 2023-07 ~ 2026-04)             │
│    2. 全球锂辉石发运至中国量 (周度, 2026-01 ~ 2026-08)                        │
│    3. 全球锂辉石发运量 (周度, 2026-01 ~ 2026-08)                              │
│                                                                              │
│  二、相关性分析结果                                                           │
│  ─────────────────────────────────────────────────────────────────────────    │
""")

for col, name in indicators.items():
    if col in correlation_results and not np.isnan(correlation_results[col].get('pearson', np.nan)):
        r = correlation_results[col]
        print(f"  {name}:")
        print(f"    有效样本: {r['n']} 个月")
        print(f"    皮尔逊相关系数: {r['pearson']:.4f}")
        print(f"    斯皮尔曼相关系数: {r['spearman']:.4f}")
        print(f"    与涨跌标签相关: {r['label_corr']:.4f}")

        if abs(r['pearson']) >= 0.4:
            print(f"    → 与结算价存在中等以上相关关系")
        elif abs(r['pearson']) >= 0.2:
            print(f"    → 与结算价存在弱相关关系")
        else:
            print(f"    → 与结算价相关性不明显")
        print()

print("""
│  三、KNN预测结果                                                              │
│  ─────────────────────────────────────────────────────────────────────────    │
│  (详见上方各指标的KNN分析输出)                                                │
│                                                                              │
│  四、结论与建议                                                               │
│  ─────────────────────────────────────────────────────────────────────────    │
│                                                                              │
│  1. 数据局限性:                                                               │
│     - 黑德兰港数据仅到2026年4月，无法覆盖最新价格走势                          │
│     - 全球发运数据仅2026年，样本量仅8个月，统计意义有限                        │
│                                                                              │
│  2. 相关性解读:                                                               │
│     - 船运量作为供给端先行指标，理论上应与价格负相关                           │
│       (发运增加 → 未来到港增加 → 供给增加 → 价格承压)                         │
│     - 但实际相关性受多种因素影响，需结合库存、需求等综合分析                    │
│                                                                              │
│  3. 使用建议:                                                                 │
│     - 船运数据可作为供给端的辅助验证指标                                       │
│     - 建议关注发运量的边际变化(环比增速)，而非绝对水平                          │
│     - 需结合其他因子(库存、开工率、需求)构建多因子模型                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
""")

print("=" * 80)
print("分析完成!")
print("=" * 80)