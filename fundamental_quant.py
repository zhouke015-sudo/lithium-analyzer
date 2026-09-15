# fundamental_quant.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import LeaveOneOut
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')


class FundamentalQuant:
    """基本面量化 - 与参考代码逻辑完全一致"""

    def __init__(self, file_path):
        self.file_path = file_path
        self.merged = None
        self.all_feature_cols = None
        self.top10_features = None
        self.correlations = None
        self.corr_df = None
        self.scaler = None
        self.X_scaled = None
        self.y = None
        self.settle_col = None
        self.latest_month = None
        self.load_data()

    def load_data(self):
        """加载并处理数据（与参考代码一致）"""
        print("📊 加载数据...")

        # ========== 1. 读取供需平衡表 ==========
        raw = pd.read_excel(self.file_path, sheet_name='供需平衡表', header=None)
        col_names = ['日期'] + [str(x) for x in raw.iloc[0, 1:].values]

        # 🔥 关键：数据从第5行（索引4）开始，不是第8行
        df = raw.iloc[4:].reset_index(drop=True)
        df.columns = col_names

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

        print(f"✅ 数据日期范围: {df['日期'].min()} ~ {df['日期'].max()}")

        # ========== 2. 找结算价列 ==========
        settle_cols = [c for c in df.columns if ('主力合约' in c and '结算价' in c)]
        if not settle_cols:
            raise ValueError("未找到主力合约结算价列")
        self.settle_col = settle_cols[0]
        print(f"✅ 使用结算价列: {self.settle_col}")

        # ========== 3. 按月聚合 ==========
        indicator_cols = [c for c in df.columns if c not in ['日期', '月份', '季度']]

        monthly_df = df.groupby('月份').agg({
            col: lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
            for col in indicator_cols
        }).reset_index()

        monthly_df['季度'] = monthly_df['月份'].apply(
            lambda m: f"{int(m.split('-')[0])}Q{(int(m.split('-')[1]) - 1) // 3 + 1}"
        )

        print(f"✅ 按月聚合完成，共 {len(monthly_df)} 个月")

        # ========== 4. 读取紫金矿业和宁德时代 ==========
        zj_df = pd.read_excel(self.file_path, sheet_name='紫金矿业', header=0)
        nd_df = pd.read_excel(self.file_path, sheet_name='宁德时代', header=0)

        zj_df['季度'] = zj_df['季度'].astype(str)
        nd_df['季度'] = nd_df['季度'].astype(str)

        zj_cols = ['净利润-同比增长', '净资产收益率', '净利率', '每股收益',
                   '营业总收入-同比增长', '销售毛利率', '每股经营现金流量', '资产负债率']
        nd_cols = zj_cols.copy()

        zj_df_r = zj_df.rename(columns={c: f'紫金_{c}' for c in zj_cols})[
            ['季度'] + [f'紫金_{c}' for c in zj_cols]]
        nd_df_r = nd_df.rename(columns={c: f'宁德_{c}' for c in nd_cols})[
            ['季度'] + [f'宁德_{c}' for c in nd_cols]]

        # ========== 5. 按月合并 ==========
        merged = monthly_df.merge(zj_df_r, on='季度', how='inner')
        merged = merged.merge(nd_df_r, on='季度', how='inner')

        # 🔥 数据截止到2026年6月（2026Q3财报未发布）
        merged = merged[merged['月份'] <= '2026-06'].reset_index(drop=True)
        print(f"✅ 合并后数据: {len(merged)} 个月，月份: {merged['月份'].tolist()}")

        # ========== 6. 生成标签（首日 vs 末日） ==========
        def get_month_label(month):
            m_data = df[df['月份'] == month].sort_values('日期').dropna(subset=[self.settle_col])
            if len(m_data) < 2:
                return np.nan
            first = m_data.iloc[0][self.settle_col]
            last = m_data.iloc[-1][self.settle_col]
            return 1 if last > first else 0

        merged['标签'] = merged['月份'].apply(get_month_label)
        merged = merged.dropna(subset=['标签'])
        merged['标签'] = merged['标签'].astype(int)

        print(f"✅ 标签生成完成: {len(merged)} 条，标签分布: 空头={sum(merged['标签'] == 0)}, 多头={sum(merged['标签'] == 1)}")

        # ========== 7. 定义全部特征列 ==========
        supply_cols = [c for c in indicator_cols if c != self.settle_col]
        all_feature_cols = supply_cols + [f'紫金_{c}' for c in zj_cols] + [f'宁德_{c}' for c in nd_cols]

        print(f"✅ 全部特征数: {len(all_feature_cols)}")

        # 填充缺失值
        for col in all_feature_cols:
            if merged[col].isnull().any():
                merged[col] = merged[col].fillna(merged[col].mean())

        self.merged = merged
        self.all_feature_cols = all_feature_cols
        self.latest_month = merged['月份'].iloc[-1]

        # ========== 8. 计算相关性 ==========
        self.calculate_correlations()

    def calculate_correlations(self):
        """计算所有特征与标签的相关系数"""
        correlations = {}
        for col in self.all_feature_cols:
            r = self.merged[col].corr(self.merged['标签'])
            correlations[col] = r

        corr_df = pd.DataFrame([
            {'特征': c, '相关系数': v, '绝对值': abs(v)}
            for c, v in correlations.items()
        ]).sort_values('绝对值', ascending=False).reset_index(drop=True)

        self.correlations = correlations
        self.corr_df = corr_df
        self.top10_features = corr_df.head(10)['特征'].tolist()

        return corr_df

    def get_top_features(self, n=10):
        if self.corr_df is None:
            self.calculate_correlations()
        return self.corr_df.head(n)['特征'].tolist()

    def get_all_correlations(self):
        """获取全部因子相关性列表"""
        if self.corr_df is None:
            self.calculate_correlations()

        result = []
        for i, (_, row) in enumerate(self.corr_df.iterrows(), 1):
            direction = "正相关" if row['相关系数'] > 0 else "负相关"
            result.append({
                '排名': i,
                '特征': row['特征'],
                '相关系数': row['相关系数'],
                '方向': direction
            })
        return result

    def get_full_correlation_table(self):
        """获取全部因子相关性 DataFrame（用于导出）"""
        if self.corr_df is None:
            self.calculate_correlations()

        result = []
        for i, (_, row) in enumerate(self.corr_df.iterrows(), 1):
            direction = "正相关" if row['相关系数'] > 0 else "负相关"
            result.append({
                '排名': i,
                '特征': row['特征'],
                '相关系数': row['相关系数'],
                '方向': direction
            })
        return pd.DataFrame(result)

    def get_default_factor_values(self):
        """因子分析默认值：最新两个月的均值"""
        if self.merged is None or len(self.merged) == 0:
            return {}
        latest_two = self.merged.tail(2)
        means = {}
        for col in self.top10_features:
            means[col] = latest_two[col].mean()
        return means

    def predict_with_top10(self, custom_values=None):
        """用 Top 10 因子进行 KNN 预测"""
        X = self.merged[self.top10_features].values
        y = self.merged['标签'].values

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.X_scaled = X_scaled
        self.y = y

        # 训练 KNN
        n_neighbors = min(5, len(X_scaled))
        knn = KNeighborsClassifier(n_neighbors=n_neighbors)
        knn.fit(X_scaled, y)

        # 构建测试样本
        if custom_values is None:
            latest_two = self.merged[self.top10_features].tail(2)
            test_X_raw = latest_two.mean().values.reshape(1, -1)
            test_label = "最新两月均值"
        else:
            test_X_raw = np.array([custom_values.get(f, 0) for f in self.top10_features]).reshape(1, -1)
            test_label = "自定义值"

        test_X = self.scaler.transform(test_X_raw)

        # 预测
        prediction = knn.predict(test_X)
        prediction_proba = knn.predict_proba(test_X)

        # 最近邻
        distances, indices = knn.kneighbors(test_X)
        neighbor_months = [str(self.merged['月份'].iloc[i]) for i in indices[0]]
        neighbor_labels = ['多头' if y[i] == 1 else '空头' for i in indices[0]]

        # 留一法交叉验证准确率
        loo = LeaveOneOut()
        correct = 0
        total = 0
        for train_idx, test_idx in loo.split(X_scaled):
            X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
            y_tr, y_te = y[train_idx], y[test_idx]
            k = min(5, len(X_tr))
            knn_loo = KNeighborsClassifier(n_neighbors=k)
            knn_loo.fit(X_tr, y_tr)
            if knn_loo.predict(X_te)[0] == y_te[0]:
                correct += 1
            total += 1

        return {
            'prediction': '多头' if prediction[0] == 1 else '空头',
            'prediction_code': int(prediction[0]),
            'prob_bear': float(prediction_proba[0][0]),
            'prob_bull': float(prediction_proba[0][1]),
            'test_label': test_label,
            'neighbor_quarters': neighbor_months,
            'neighbor_labels': neighbor_labels,
            'accuracy': correct / total if total > 0 else 0,
            'total_samples': len(self.merged),
            'feature_count': len(self.top10_features),
            'feature_list': self.top10_features,
            'latest_month': self.latest_month,
            'all_feature_count': len(self.all_feature_cols)
        }

    def get_summary(self, result=None):
        if result is None:
            return "请先执行预测"

        summary = f"""
{'=' * 60}
📊 因子分析预测结果
{'=' * 60}

📅 数据区间: 截至 {result['latest_month']}  ({result['total_samples']} 个月)
📊 全部因子数: {result['all_feature_count']}  |  使用 Top {result['feature_count']} 因子
📊 输入方式: {result['test_label']}

🎯 预测结果: {result['prediction']}
    - 空头概率: {result['prob_bear']:.1%}
    - 多头概率: {result['prob_bull']:.1%}

📈 最近相似月份:
"""
        for i, (q, label) in enumerate(zip(result['neighbor_quarters'], result['neighbor_labels'])):
            summary += f"    {i + 1}. {q} → {label}\n"

        summary += f"""
📊 模型准确率 (留一法): {result['accuracy']:.1%}
📊 训练样本数: {result['total_samples']}
{'=' * 60}

💡 建议: 
"""
        if result['prediction'] == '多头':
            summary += "   当前因子组合下，预测价格上涨，可考虑多头配置"
        else:
            summary += "   当前因子组合下，预测价格下跌，可考虑空头配置或套保"
        return summary