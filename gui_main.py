# gui_main.py
import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon

from data_processor import read_data, calculate_stats, INDICATORS, read_sheet_data
from conduction_quant_v2 import ConductionQuantV2
from fundamental_quant import FundamentalQuant
from futures_api import FuturesAPI

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC', 'Heiti SC']
plt.rcParams['axes.unicode_minus'] = False


class DataLoaderThread(QThread):
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            dates, data_dict = read_data(self.file_path, '供需平衡表')
            self.finished.emit(dates, data_dict)
        except Exception as e:
            self.error.emit(str(e))


class StatsCalculatorThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, dates, data_dict, indicators):
        super().__init__()
        self.dates = dates
        self.data_dict = data_dict
        self.indicators = indicators

    def run(self):
        all_stats = {}
        for name in self.indicators:
            stats = calculate_stats(self.data_dict[name], self.dates)
            if stats:
                all_stats[name] = stats
        self.finished.emit(all_stats)


class FundamentalQuantThread(QThread):
    """基本面量化 - 只计算相关性"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            fq = FundamentalQuant(self.file_path)
            all_corr = fq.get_all_correlations()
            top_features = fq.get_top_features(10)
            self.finished.emit({
                'correlations': all_corr,
                'top_features': top_features,
                'feature_count': len(fq.all_feature_cols),
                'total_samples': len(fq.merged),
                'latest_month': fq.latest_month
            })
        except Exception as e:
            import traceback
            self.error.emit(str(e) + "\n" + traceback.format_exc())


class FactorAnalysisThread(QThread):
    """因子分析 - KNN预测"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path, custom_values=None):
        super().__init__()
        self.file_path = file_path
        self.custom_values = custom_values

    def run(self):
        try:
            fq = FundamentalQuant(self.file_path)
            default_vals = fq.get_default_factor_values()

            if self.custom_values is None:
                values = None
            else:
                values = self.custom_values

            result = fq.predict_with_top10(custom_values=values)
            self.finished.emit({
                'result': result,
                'top_features': fq.top10_features,
                'default_values': default_vals,
                'correlations': fq.get_all_correlations()[:10],
                'all_feature_count': len(fq.all_feature_cols),
                'total_samples': len(fq.merged),
                'latest_month': fq.latest_month
            })
        except Exception as e:
            import traceback
            self.error.emit(str(e) + "\n" + traceback.format_exc())


class LithiumAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dates = None
        self.data_dict = None
        self.all_stats = {}
        self.current_file = None

        self.conduction_calculator = None
        self.futures_api = FuturesAPI()
        self.conduction_inputs = {
            'ore_price': None,
            'battery_price': None,
            'industrial_price': None,
            'futures_price': None,
        }

        self.stats_chart_type = '涨跌幅'
        self.history_period = '上市至今'

        # 基本面量化
        self.correlation_result = None
        self.corr_data = []

        # 因子分析
        self.factor_result = None
        self.factor_top_features = []
        self.factor_input_widgets = {}
        self.factor_default_values = {}
        self.factor_initial_run = False

        self.initUI()

    def initUI(self):
        self.setWindowTitle('🔋 碳酸锂数据分析工具 v2.0')
        self.setGeometry(50, 50, 1600, 950)

        self.createMenuBar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # ========== 左侧面板 ==========
        left_panel = QWidget()
        left_panel.setMaximumWidth(420)
        left_panel.setMinimumWidth(340)
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        # 1. 文件加载
        file_group = QGroupBox("📂 数据加载")
        file_layout = QVBoxLayout()
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("color: gray; padding: 5px;")
        self.file_path_label.setWordWrap(True)

        load_btn = QPushButton("📁 加载Excel文件")
        load_btn.clicked.connect(self.loadFile)
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white; padding: 8px; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)

        self.file_info_label = QLabel("状态: 未加载")
        self.file_info_label.setStyleSheet("color: #ff6b6b; padding: 5px;")

        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(load_btn)
        file_layout.addWidget(self.file_info_label)
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)

        # 2. 功能模式
        mode_group = QGroupBox("🔧 功能模式")
        mode_layout = QVBoxLayout()

        self.mode_button_group = QButtonGroup()

        self.mode_history_btn = QPushButton("📈 历史分位")
        self.mode_history_btn.setCheckable(True)
        self.mode_history_btn.setChecked(True)
        self.mode_history_btn.clicked.connect(lambda: self.switchMode('history'))

        self.mode_stats_btn = QPushButton("📊 统计信息")
        self.mode_stats_btn.setCheckable(True)
        self.mode_stats_btn.clicked.connect(lambda: self.switchMode('stats'))

        self.mode_conduction_btn = QPushButton("🔬 传导量化")
        self.mode_conduction_btn.setCheckable(True)
        self.mode_conduction_btn.clicked.connect(lambda: self.switchMode('conduction'))

        self.mode_fundamental_btn = QPushButton("📈 基本面量化")
        self.mode_fundamental_btn.setCheckable(True)
        self.mode_fundamental_btn.clicked.connect(lambda: self.switchMode('fundamental'))

        self.mode_factor_btn = QPushButton("🧩 因子分析")
        self.mode_factor_btn.setCheckable(True)
        self.mode_factor_btn.clicked.connect(lambda: self.switchMode('factor'))

        for btn in [self.mode_history_btn, self.mode_stats_btn, self.mode_conduction_btn,
                    self.mode_fundamental_btn, self.mode_factor_btn]:
            self.mode_button_group.addButton(btn)

        btn_style = """
            QPushButton {
                padding: 6px; border: 2px solid #ddd; border-radius: 5px;
                background-color: #f5f5f5; font-weight: bold;
            }
            QPushButton:checked {
                background-color: #2196F3; color: white; border-color: #1976D2;
            }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:checked:hover { background-color: #1976D2; }
        """

        for btn in [self.mode_history_btn, self.mode_stats_btn, self.mode_conduction_btn,
                    self.mode_fundamental_btn, self.mode_factor_btn]:
            btn.setStyleSheet(btn_style)
            mode_layout.addWidget(btn)

        mode_group.setLayout(mode_layout)
        left_layout.addWidget(mode_group)

        # 3. 指标选择
        indicator_group = QGroupBox("📊 选择指标")
        indicator_layout = QVBoxLayout()

        indicator_grid = QGridLayout()
        self.indicator_checkboxes = {}
        row, col = 0, 0
        for name in INDICATORS.keys():
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self.onIndicatorChanged)
            self.indicator_checkboxes[name] = cb
            indicator_grid.addWidget(cb, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

        indicator_layout.addLayout(indicator_grid)

        stats_chart_layout = QHBoxLayout()
        stats_chart_layout.addWidget(QLabel("图表类型:"))
        self.stats_chart_combo = QComboBox()
        self.stats_chart_combo.addItems(['涨跌幅', '波动率', '平均值'])
        self.stats_chart_combo.currentTextChanged.connect(self.onStatsChartTypeChanged)
        self.stats_chart_combo.setVisible(False)
        stats_chart_layout.addWidget(self.stats_chart_combo)
        stats_chart_layout.addStretch()
        indicator_layout.addLayout(stats_chart_layout)

        history_period_layout = QHBoxLayout()
        history_period_layout.addWidget(QLabel("历史周期:"))
        self.history_period_combo = QComboBox()
        self.history_period_combo.addItems(['上市至今', '近一年', '近一月', '近一周'])
        self.history_period_combo.currentTextChanged.connect(self.onHistoryPeriodChanged)
        history_period_layout.addWidget(self.history_period_combo)
        history_period_layout.addStretch()
        indicator_layout.addLayout(history_period_layout)

        select_btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(lambda: self.selectAll(True))
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(lambda: self.selectAll(False))
        select_btn_layout.addWidget(select_all_btn)
        select_btn_layout.addWidget(deselect_all_btn)
        indicator_layout.addLayout(select_btn_layout)

        indicator_group.setLayout(indicator_layout)
        self.indicator_group = indicator_group
        left_layout.addWidget(indicator_group)

        # 4. 传导量化输入
        conduction_input_group = QGroupBox("🔬 传导量化输入")
        conduction_input_layout = QVBoxLayout()

        for label_text, attr_name in [
            ("澳大利亚锂辉石精矿:", "ore_input"),
            ("电池级碳酸锂:", "battery_input"),
            ("工业级碳酸锂:", "industrial_input"),
            ("主力合约实时价:", "futures_input"),
        ]:
            layout = QHBoxLayout()
            layout.addWidget(QLabel(label_text))
            input_box = QLineEdit()
            input_box.setPlaceholderText("元/吨" if "锂辉石" not in label_text else "美元/吨")
            input_box.textChanged.connect(self.onConductionInputChanged)
            setattr(self, attr_name, input_box)
            layout.addWidget(input_box)
            conduction_input_layout.addLayout(layout)

        modify_btn = QPushButton("📝 修改价格")
        modify_btn.clicked.connect(self.updateConductionInputs)
        conduction_input_layout.addWidget(modify_btn)

        self.conduction_status_label = QLabel("等待输入价格...")
        self.conduction_status_label.setStyleSheet("color: #ff9800; padding: 5px;")
        conduction_input_layout.addWidget(self.conduction_status_label)

        self.countdown_label = QLabel("💡 点击'修改价格'更新数据")
        self.countdown_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2196F3;")
        conduction_input_layout.addWidget(self.countdown_label)

        conduction_input_group.setLayout(conduction_input_layout)
        self.conduction_input_group = conduction_input_group
        self.conduction_input_group.setVisible(False)
        left_layout.addWidget(conduction_input_group)

        # 5. 因子分析输入
        factor_input_group = QGroupBox("🧩 因子分析输入（Top 10 因子）")
        factor_input_layout = QVBoxLayout()

        self.factor_scroll_area = QScrollArea()
        self.factor_scroll_area.setWidgetResizable(True)
        self.factor_scroll_widget = QWidget()
        self.factor_scroll_layout = QVBoxLayout(self.factor_scroll_widget)
        self.factor_scroll_area.setWidget(self.factor_scroll_widget)
        factor_input_layout.addWidget(self.factor_scroll_area)

        self.factor_input_widgets = {}

        factor_btn_layout = QHBoxLayout()
        factor_run_btn = QPushButton("🚀 运行因子分析")
        factor_run_btn.clicked.connect(self.runFactorAnalysis)
        factor_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; padding: 8px;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        factor_btn_layout.addWidget(factor_run_btn)

        factor_reset_btn = QPushButton("🔄 重置为最新两月均值")
        factor_reset_btn.clicked.connect(self.resetFactorInputs)
        factor_btn_layout.addWidget(factor_reset_btn)

        factor_input_layout.addLayout(factor_btn_layout)

        self.factor_status_label = QLabel("💡 默认值为最新两月均值，可直接修改")
        self.factor_status_label.setStyleSheet("color: #666666; padding: 5px;")
        factor_input_layout.addWidget(self.factor_status_label)

        factor_input_group.setLayout(factor_input_layout)
        self.factor_input_group = factor_input_group
        self.factor_input_group.setVisible(False)
        left_layout.addWidget(factor_input_group)

        # 6. 统计信息显示
        stats_group = QGroupBox("📈 统计信息")
        stats_layout = QVBoxLayout()
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(250)
        self.stats_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        stats_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_layout)
        self.stats_group = stats_group
        left_layout.addWidget(stats_group)

        # 7. 操作按钮
        btn_layout = QVBoxLayout()
        self.update_btn = QPushButton("🔄 更新图表")
        self.update_btn.clicked.connect(self.updateCharts)
        self.update_btn.setEnabled(False)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; padding: 10px;
                border-radius: 5px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #cccccc; }
        """)

        # 🔥 修改：导出统计表格 → 导出因子相关性
        export_btn = QPushButton("💾 导出因子相关性")
        export_btn.clicked.connect(self.exportAllCorrelations)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800; color: white; padding: 8px;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)

        btn_layout.addWidget(self.update_btn)
        btn_layout.addWidget(export_btn)
        left_layout.addLayout(btn_layout)

        left_layout.addStretch()

        # ========== 右侧图表区域 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        self.figure = plt.figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)
        main_layout.setStretchFactor(left_panel, 1)
        main_layout.setStretchFactor(right_panel, 3)

        self.showWelcomeMessage()
        self.current_mode = 'history'

    def createMenuBar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('文件')
        open_action = QAction('打开文件', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.loadFile)
        file_menu.addAction(open_action)
        file_menu.addSeparator()

        export_action = QAction('导出统计表格', self)
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(self.exportStats)
        file_menu.addAction(export_action)

        export_corr_action = QAction('导出全部因子相关性', self)
        export_corr_action.setShortcut('Ctrl+Shift+E')
        export_corr_action.triggered.connect(self.exportAllCorrelations)
        file_menu.addAction(export_corr_action)

        file_menu.addSeparator()
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu('视图')
        reset_view_action = QAction('重置视图', self)
        reset_view_action.triggered.connect(self.resetView)
        view_menu.addAction(reset_view_action)

        help_menu = menubar.addMenu('帮助')
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.showAbout)
        help_menu.addAction(about_action)

    def onHistoryPeriodChanged(self, period):
        self.history_period = period
        if self.current_mode == 'history' and self.dates is not None:
            self.plotHistoryCharts()

    def switchMode(self, mode):
        self.current_mode = mode

        if mode == 'history':
            self.mode_history_btn.setChecked(True)
            self.indicator_group.setVisible(True)
            self.conduction_input_group.setVisible(False)
            self.factor_input_group.setVisible(False)
            self.stats_group.setVisible(False)
            self.stats_chart_combo.setVisible(False)
            self.history_period_combo.setVisible(True)
            if self.dates is not None:
                self.plotHistoryCharts()

        elif mode == 'stats':
            self.mode_stats_btn.setChecked(True)
            self.indicator_group.setVisible(True)
            self.conduction_input_group.setVisible(False)
            self.factor_input_group.setVisible(False)
            self.stats_group.setVisible(True)
            self.stats_chart_combo.setVisible(True)
            self.history_period_combo.setVisible(False)
            if self.all_stats:
                self.updateStatsDisplay()
                self.plotStatsCharts()

        elif mode == 'conduction':
            self.mode_conduction_btn.setChecked(True)
            self.indicator_group.setVisible(False)
            self.conduction_input_group.setVisible(True)
            self.factor_input_group.setVisible(False)
            self.stats_group.setVisible(False)
            self.stats_chart_combo.setVisible(False)
            self.history_period_combo.setVisible(False)
            self.startConduction()

        elif mode == 'fundamental':
            self.mode_fundamental_btn.setChecked(True)
            self.indicator_group.setVisible(False)
            self.conduction_input_group.setVisible(False)
            self.factor_input_group.setVisible(False)
            self.stats_group.setVisible(False)
            self.stats_chart_combo.setVisible(False)
            self.history_period_combo.setVisible(False)
            self.runFundamentalQuant()

        elif mode == 'factor':
            self.mode_factor_btn.setChecked(True)
            self.indicator_group.setVisible(False)
            self.conduction_input_group.setVisible(False)
            self.factor_input_group.setVisible(True)
            self.stats_group.setVisible(False)
            self.stats_chart_combo.setVisible(False)
            self.history_period_combo.setVisible(False)
            self.initFactorInputs()

    def onStatsChartTypeChanged(self, chart_type):
        self.stats_chart_type = chart_type
        if self.current_mode == 'stats' and self.all_stats:
            self.plotStatsCharts()

    def loadFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Excel数据文件", "",
            "Excel文件 (*.xlsx *.xls);;所有文件 (*.*)"
        )
        if not file_path:
            return

        self.current_file = file_path
        self.file_path_label.setText(os.path.basename(file_path))
        self.file_info_label.setText("状态: 加载中...")
        self.file_info_label.setStyleSheet("color: #ff9800; padding: 5px;")
        self.statusBar.showMessage(f"正在加载文件: {os.path.basename(file_path)}...")

        self.loader_thread = DataLoaderThread(file_path)
        self.loader_thread.finished.connect(self.onDataLoaded)
        self.loader_thread.error.connect(self.onLoadError)
        self.loader_thread.start()

    def onDataLoaded(self, dates, data_dict):
        self.dates = dates
        self.data_dict = data_dict

        self.file_info_label.setText(f"✅ 加载成功! 共 {len(dates)} 条数据")
        self.file_info_label.setStyleSheet("color: #4CAF50; padding: 5px;")
        self.statusBar.showMessage(f"加载成功: {len(dates)} 条数据")

        self.update_btn.setEnabled(True)
        self.updateCharts()

    def onLoadError(self, error_msg):
        self.file_info_label.setText(f"❌ 加载失败")
        self.file_info_label.setStyleSheet("color: #ff6b6b; padding: 5px;")
        self.statusBar.showMessage(f"加载失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"加载文件失败：\n{error_msg}")

    def onIndicatorChanged(self):
        if self.current_mode == 'history':
            self.plotHistoryCharts()
        elif self.current_mode == 'stats':
            if self.all_stats:
                self.updateStatsDisplay()
                self.plotStatsCharts()

    def selectAll(self, checked):
        for cb in self.indicator_checkboxes.values():
            cb.setChecked(checked)
        self.onIndicatorChanged()

    def updateCharts(self):
        if self.dates is None or self.data_dict is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        selected_indicators = [name for name, cb in self.indicator_checkboxes.items() if cb.isChecked()]
        self.statusBar.showMessage("正在计算统计指标...")

        self.calc_thread = StatsCalculatorThread(self.dates, self.data_dict, selected_indicators)
        self.calc_thread.finished.connect(self.onStatsCalculated)
        self.calc_thread.start()

    def onStatsCalculated(self, all_stats):
        self.all_stats = all_stats
        if self.current_mode == 'history':
            self.plotHistoryCharts()
        elif self.current_mode == 'stats':
            self.updateStatsDisplay()
            self.plotStatsCharts()
        self.statusBar.showMessage("更新完成")

    # ==================== 历史分位 ====================
    def plotHistoryCharts(self):
        if not self.all_stats:
            return
        self.figure.clear()

        selected_indicators = [name for name, cb in self.indicator_checkboxes.items()
                               if cb.isChecked() and name in self.all_stats]
        n = len(selected_indicators)
        if n == 0:
            self.showWelcomeMessage()
            return

        cols = 2
        rows = (n + 1) // 2
        if n == 1:
            rows, cols = 1, 1
        elif n == 2:
            rows, cols = 1, 2

        for idx, name in enumerate(selected_indicators):
            ax = self.figure.add_subplot(rows, cols, idx + 1)
            self.plotHistorySingleChart(ax, name)

        self.figure.tight_layout()
        self.canvas.draw()

    def plotHistorySingleChart(self, ax, name):
        data = self.data_dict[name]
        config = INDICATORS[name]

        series = pd.Series(data, index=self.dates)
        valid_data = series.dropna()

        if len(valid_data) < 2:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            return

        period = self.history_period
        if period == '近一周':
            valid_data = valid_data.iloc[:5] if len(valid_data) >= 5 else valid_data
        elif period == '近一月':
            valid_data = valid_data.iloc[:22] if len(valid_data) >= 22 else valid_data
        elif period == '近一年':
            valid_data = valid_data.iloc[:252] if len(valid_data) >= 252 else valid_data

        if len(valid_data) < 2:
            ax.text(0.5, 0.5, '该周期数据不足', ha='center', va='center', transform=ax.transAxes)
            return

        plot_series = valid_data.iloc[::-1]
        plot_dates = plot_series.index

        ax.plot(plot_dates, plot_series.values, color=config['color'], linewidth=1.5, label=name)
        ax.set_xlabel('日期', fontsize=9)
        ax.set_ylabel(f'{name} ({config["unit"]})', fontsize=9, color=config['color'])
        ax.tick_params(axis='y', labelcolor=config['color'])
        ax.grid(True, alpha=0.3)

        step = max(1, len(plot_dates) // 20)
        xticks = plot_dates[::step]
        ax.set_xticks(xticks)
        ax.set_xticklabels(xticks, rotation=45, ha='right', fontsize=7)

        ax2 = ax.twinx()
        sorted_data = np.sort(valid_data.values)
        percentiles = []
        for val in valid_data.values:
            pct = np.searchsorted(sorted_data, val) / len(sorted_data) * 100
            percentiles.append(pct)
        plot_percentiles = percentiles[::-1]

        ax2.plot(plot_dates, plot_percentiles, color='#FF6B6B', linewidth=1.0,
                 linestyle='--', alpha=0.7, label='分位数(%)')
        ax2.set_ylabel('分位数 (%)', fontsize=9, color='#FF6B6B')
        ax2.tick_params(axis='y', labelcolor='#FF6B6B')
        ax2.set_ylim(0, 100)

        for pct in [25, 50, 75]:
            ax2.axhline(y=pct, color='#FF6B6B', linestyle=':', alpha=0.3, linewidth=0.8)

        if len(plot_series) > 0:
            last_date = plot_series.index[-1]
            last_price = plot_series.values[-1]
            last_pct = plot_percentiles[-1] if len(plot_percentiles) > 0 else 50

            ax.scatter(last_date, last_price, color=config['color'], s=80,
                       zorder=5, marker='o', edgecolor='white', linewidth=2)
            ax.annotate(f'{last_price:.0f}', xy=(last_date, last_price),
                        xytext=(5, 10), textcoords='offset points', fontsize=8, fontweight='bold')

            ax2.scatter(last_date, last_pct, color='#FF6B6B', s=60,
                        zorder=5, marker='s', edgecolor='white', linewidth=2)
            ax2.annotate(f'{last_pct:.1f}%', xy=(last_date, last_pct),
                         xytext=(5, -15), textcoords='offset points',
                         fontsize=8, fontweight='bold', color='#FF6B6B')

        ax.set_title(f'{name} - {period}', fontsize=10, fontweight='bold')

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=7)

    # ==================== 统计信息 ====================
    def plotStatsCharts(self):
        if not self.all_stats:
            return
        self.figure.clear()

        selected_indicators = [name for name, cb in self.indicator_checkboxes.items()
                               if cb.isChecked() and name in self.all_stats]
        if not selected_indicators:
            self.showWelcomeMessage()
            return

        chart_type = self.stats_chart_type
        ax = self.figure.add_subplot(111)

        names, week_values, month_values, year_values = [], [], [], []

        for name in selected_indicators:
            stats = self.all_stats[name]
            names.append(name)
            if chart_type == '涨跌幅':
                week_values.append(stats['week_return'])
                month_values.append(stats['month_return'])
                year_values.append(stats['year_return'])
                ylabel, title = '涨跌幅 (%)', '各指标涨跌幅对比'
            elif chart_type == '波动率':
                week_values.append(stats['week_volatility'])
                month_values.append(stats['month_volatility'])
                year_values.append(stats['year_volatility'])
                ylabel, title = '波动率 (%)', '各指标波动率对比'
            else:
                week_values.append(stats['week_avg'])
                month_values.append(stats['month_avg'])
                year_values.append(stats['year_avg'])
                ylabel, title = '平均值', '各指标平均值对比'

        x = np.arange(len(names))
        width = 0.25
        bars1 = ax.bar(x - width, week_values, width, label='近一周', color='#4CAF50', alpha=0.8)
        bars2 = ax.bar(x, month_values, width, label='近一月', color='#2196F3', alpha=0.8)
        bars3 = ax.bar(x + width, year_values, width, label='近一年', color='#FF9800', alpha=0.8)

        ax.set_xlabel('指标', fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=15, ha='right', fontsize=9)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend(fontsize=9, loc='upper left')

        for bars, vals in [(bars1, week_values), (bars2, month_values), (bars3, year_values)]:
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + (abs(val) * 0.05 if val >= 0 else abs(val) * 0.05),
                        f'{val:.1f}', ha='center', va='bottom' if val >= 0 else 'top', fontsize=7)

        self.figure.tight_layout()
        self.canvas.draw()

    def updateStatsDisplay(self):
        if not self.all_stats:
            self.stats_text.setText("暂无数据")
            return

        selected_indicators = [name for name, cb in self.indicator_checkboxes.items()
                               if cb.isChecked() and name in self.all_stats]

        text = ""
        for name in selected_indicators:
            stats = self.all_stats[name]
            unit = INDICATORS[name]['unit']

            text += f"📊 {name}\n{'─' * 50}\n"
            text += f"📅 最新日期: {stats['current_date']}\n"
            text += f"💰 当前价格: {stats['current_price']:.2f} {unit}\n"
            text += f"📊 数据量: {stats['data_count']} 条\n"
            text += f"📉 历史最低: {stats['min_val']:.2f} {unit}\n"
            text += f"📈 历史最高: {stats['max_val']:.2f} {unit}\n\n"
            text += f"📈 涨跌幅:\n   近一周: {stats['week_return']:+.2f}%\n"
            text += f"   近一月: {stats['month_return']:+.2f}%\n"
            text += f"   近一年: {stats['year_return']:+.2f}%\n\n"
            text += f"📊 波动率 (年化):\n   近一周: {stats['week_volatility']:.2f}%\n"
            text += f"   近一月: {stats['month_volatility']:.2f}%\n"
            text += f"   近一年: {stats['year_volatility']:.2f}%\n\n"
            text += f"📐 平均值:\n   近一周: {stats['week_avg']:.2f} {unit}\n"
            text += f"   近一月: {stats['month_avg']:.2f} {unit}\n"
            text += f"   近一年: {stats['year_avg']:.2f} {unit}\n\n"
            text += f"🎯 支撑位与阻力位:\n"
            if stats['month_support']:
                text += f"   近一月支撑: {stats['month_support']:.2f} {unit}\n"
            if stats['month_resistance']:
                text += f"   近一月阻力: {stats['month_resistance']:.2f} {unit}\n"
            if stats['year_support']:
                text += f"   近一年支撑: {stats['year_support']:.2f} {unit}\n"
            if stats['year_resistance']:
                text += f"   近一年阻力: {stats['year_resistance']:.2f} {unit}\n"

            if stats["current_price"] > stats["year_avg"]:
                pct = (stats["current_price"] - stats["year_avg"]) / stats["year_avg"] * 100
                text += f"\n💡 当前价格高于近一年均值 {pct:+.2f}%，处于偏强位置\n"
            else:
                pct = (stats["year_avg"] - stats["current_price"]) / stats["year_avg"] * 100
                text += f"\n💡 当前价格低于近一年均值 {pct:+.2f}%，处于偏弱位置\n"
            text += "\n"

        self.stats_text.setText(text)

    # ==================== 传导量化 ====================
    def startConduction(self):
        if self.dates is None or self.data_dict is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        self.conduction_calculator = ConductionQuantV2(self.dates, self.data_dict)
        if all(v is not None for v in self.conduction_inputs.values()):
            self.updateConductionDisplay()
        else:
            self.showConductionWelcome()
        self.countdown_label.setText("💡 点击'修改价格'更新数据")

    def onConductionInputChanged(self):
        inputs = [self.ore_input.text().strip(), self.battery_input.text().strip(),
                  self.industrial_input.text().strip(), self.futures_input.text().strip()]
        if all(inputs):
            self.conduction_status_label.setText("✅ 输入完整，点击'修改价格'更新")
            self.conduction_status_label.setStyleSheet("color: #4CAF50; padding: 5px;")
        else:
            self.conduction_status_label.setText("⏳ 请输入所有四个价格")
            self.conduction_status_label.setStyleSheet("color: #ff9800; padding: 5px;")

    def updateConductionInputs(self):
        try:
            self.conduction_inputs['ore_price'] = float(self.ore_input.text().strip())
            self.conduction_inputs['battery_price'] = float(self.battery_input.text().strip())
            self.conduction_inputs['industrial_price'] = float(self.industrial_input.text().strip())
            self.conduction_inputs['futures_price'] = float(self.futures_input.text().strip())

            self.futures_api.update_futures_data(self.conduction_inputs['futures_price'])
            self.conduction_status_label.setText(f"✅ 价格已更新")
            self.conduction_status_label.setStyleSheet("color: #4CAF50; padding: 5px;")
            self.updateConductionDisplay()
        except ValueError:
            QMessageBox.warning(self, "错误", "请输入有效的数字")

    def updateConductionDisplay(self):
        if self.conduction_calculator is None:
            return
        if not all(v is not None for v in self.conduction_inputs.values()):
            self.showConductionWelcome()
            return

        try:
            futures_data = self.futures_api.get_futures_with_cache()
            futures_price = futures_data['price']
            self.conduction_calculator.set_futures_data(futures_data)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取期货数据失败：{str(e)}")
            return

        result = self.conduction_calculator.calculate(
            self.conduction_inputs['ore_price'],
            self.conduction_inputs['battery_price'],
            self.conduction_inputs['industrial_price'],
            futures_price
        )
        if result is None:
            return

        self.figure.clear()
        gs = self.figure.add_gridspec(3, 1, height_ratios=[2.5, 1.2, 0.8])

        ax_table = self.figure.add_subplot(gs[0])
        ax_table.axis('off')

        table_data = [
            ['指标', '当前值', '历史均值', '标准差', 'Z-Score', '分位'],
            ['澳大利亚锂辉石精矿', f"{result['ore_price']:.2f}", f"{result['mean_ore']:.2f}",
             f"{result.get('std_ore', 0):.2f}", f"{result['z_ore']:+.4f}", f"{result.get('percentile_ore', 50):.0f}%"],
            ['电池级碳酸锂', f"{result['battery_price']:.2f}", f"{result['mean_battery']:.2f}",
             f"{result.get('std_battery', 0):.2f}", f"{result['z_battery']:+.4f}", f"{result.get('percentile_battery', 50):.0f}%"],
            ['工业级碳酸锂', f"{result['industrial_price']:.2f}", f"{result['mean_industrial']:.2f}",
             f"{result.get('std_industrial', 0):.2f}", f"{result['z_industrial']:+.4f}", f"{result.get('percentile_industrial', 50):.0f}%"],
            ['主力合约结算价', f"{result['futures_price']:.2f}", f"{result['mean_futures']:.2f}",
             f"{result.get('std_futures', 0):.2f}", f"{result['z_futures']:+.4f}", f"{result.get('percentile_futures', 50):.0f}%"],
        ]

        table = ax_table.table(cellText=table_data, loc='center', cellLoc='center',
                               colWidths=[0.15, 0.15, 0.15, 0.12, 0.2, 0.12])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.8)

        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_facecolor('#2196F3')
                cell.set_text_props(color='white', fontweight='bold')
            elif i % 2 == 0:
                cell.set_facecolor('#f5f5f5')
            cell.set_edgecolor('#cccccc')

        ax_table.text(0.5, 0.95, '🔬 传导量化分析报告', ha='center', va='center', fontsize=16, fontweight='bold')
        ax_table.text(0.5, 0.90, f"更新时间: {result['datetime']}  |  数据周期: 上市至今",
                      ha='center', va='center', fontsize=9, color='gray')
        ax_table.text(0.5, 0.06,
                      '方法说明: Z-Score = (当前值 - 历史均值) / 标准差  |  CDI = 四个Z-Score等权平均',
                      ha='center', va='center', fontsize=9, color='#666666', style='italic')

        ax_chart = self.figure.add_subplot(gs[1])
        categories = ['澳大利亚锂辉石精矿', '电池级碳酸锂', '工业级碳酸锂', '主力合约']
        z_values = [result['z_ore'], result['z_battery'], result['z_industrial'], result['z_futures']]
        colors_bar = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']

        bars = ax_chart.bar(categories, z_values, color=colors_bar, alpha=0.7, edgecolor='black', linewidth=0.5)
        ax_chart.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax_chart.axhline(y=1.5, color='orange', linestyle='--', alpha=0.5, linewidth=0.8, label='轻度阈值 (±1.5)')
        ax_chart.axhline(y=2.0, color='red', linestyle='--', alpha=0.5, linewidth=0.8, label='强烈阈值 (±2.0)')
        ax_chart.axhline(y=-1.5, color='orange', linestyle='--', alpha=0.5, linewidth=0.8)
        ax_chart.axhline(y=-2.0, color='red', linestyle='--', alpha=0.5, linewidth=0.8)
        ax_chart.set_ylabel('Z-Score', fontsize=10)
        ax_chart.set_title('各指标Z-Score偏离度对比', fontsize=12, fontweight='bold')
        ax_chart.grid(True, alpha=0.3, axis='y')
        ax_chart.legend(loc='upper right', fontsize=7)

        for bar, val in zip(bars, z_values):
            ax_chart.text(bar.get_x() + bar.get_width() / 2,
                          bar.get_height() + (0.15 if val >= 0 else -0.35),
                          f'{val:+.2f}', ha='center', va='bottom' if val >= 0 else 'top',
                          fontsize=9, fontweight='bold')

        ax_signal = self.figure.add_subplot(gs[2])
        ax_signal.axis('off')

        signal_color = '#4CAF50' if result['direction'] == 'BUY' else '#f44336' if result['direction'] == 'SELL' else '#FF9800'
        ax_signal.text(0.15, 0.5, '综合偏离指数 (CDI)', ha='center', va='center', fontsize=12, fontweight='bold')
        ax_signal.text(0.15, 0.2, f'CDI = {result["cdi"]:+.4f}', ha='center', va='center', fontsize=14,
                       fontweight='bold', color='#2196F3')
        ax_signal.text(0.50, 0.5, '交易信号', ha='center', va='center', fontsize=12, fontweight='bold')
        ax_signal.text(0.50, 0.2, f'{result["signal"]}', ha='center', va='center', fontsize=14,
                       fontweight='bold', color=signal_color)
        ax_signal.text(0.80, 0.5, '权重配置', ha='center', va='center', fontsize=12, fontweight='bold')
        ax_signal.text(0.80, 0.2, '25% / 25% / 25% / 25%', ha='center', va='center', fontsize=11, color='#666666')
        ax_signal.text(0.5, -0.3,
                       'CDI值区间说明: >2.0强烈高估→看空 | 1.5~2.0轻度高估→轻仓试空 | -1.5~1.5正常→观望 | -2.0~-1.5轻度低估→轻仓试多 | <-2.0强烈低估→看多',
                       ha='center', va='center', fontsize=8, color='#888888', style='italic')

        self.figure.tight_layout()
        self.canvas.draw()

    def showConductionWelcome(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.6, '🔬 传导量化分析', ha='center', va='center', fontsize=24, fontweight='bold')
        ax.text(0.5, 0.4, '请在左侧输入四个价格后点击"修改价格"', ha='center', va='center', fontsize=14, color='gray')
        ax.text(0.5, 0.3, '澳大利亚锂辉石精矿 + 电池级碳酸锂 + 工业级碳酸锂 + 主力合约实时价',
                ha='center', va='center', fontsize=12, color='gray')
        ax.axis('off')
        self.canvas.draw()

    # ==================== 基本面量化（只显示前20个因子） ====================
    def runFundamentalQuant(self):
        if self.current_file is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        self.statusBar.showMessage("正在计算全部因子相关性...")
        self.fundamental_thread = FundamentalQuantThread(self.current_file)
        self.fundamental_thread.finished.connect(self.onFundamentalComplete)
        self.fundamental_thread.error.connect(self.onFundamentalError)
        self.fundamental_thread.start()

    def onFundamentalComplete(self, result):
        """基本面量化 - 显示前20个因子相关性表格"""
        self.correlation_result = result
        self.corr_data = result.get('correlations', [])

        feature_count = result.get('feature_count', 0)
        total_samples = result.get('total_samples', 0)
        latest_month = result.get('latest_month', '')

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis('off')

        # 只显示前20个
        top20 = self.corr_data[:20]

        # 标题
        ax.text(0.5, 0.98,
                f'📈 基本面量化 - 全部因子相关性分析（共 {feature_count} 个因子）',
                ha='center', va='top', fontsize=15, fontweight='bold')
        ax.text(0.5, 0.94,
                f'数据区间: 截至 {latest_month}  |  样本数: {total_samples} 个月  |  显示前 20 个因子',
                ha='center', va='top', fontsize=10, color='gray')

        # 表格
        table_data = [['排名', '特征名称', '相关系数', '方向']]
        for item in top20:
            table_data.append([
                str(item['排名']),
                item['特征'][:48],
                f"{item['相关系数']:+.4f}",
                item['方向']
            ])

        table = ax.table(cellText=table_data, loc='center', cellLoc='left',
                         colWidths=[0.08, 0.62, 0.15, 0.15],
                         bbox=[0.05, 0.12, 0.90, 0.78])
        table.auto_set_font_size(False)
        table.set_fontsize(10)

        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_facecolor('#2196F3')
                cell.set_text_props(color='white', fontweight='bold')
                cell.set_height(0.06)
            else:
                if j == 3:
                    text = cell.get_text().get_text()
                    if '正相关' in text:
                        cell.set_facecolor('#E8F5E9')
                        cell.set_text_props(color='#2E7D32', fontweight='bold')
                    elif '负相关' in text:
                        cell.set_facecolor('#FFEBEE')
                        cell.set_text_props(color='#C62828', fontweight='bold')
                elif i % 2 == 0:
                    cell.set_facecolor('#f5f5f5')
                cell.set_height(0.035)
            cell.set_edgecolor('#cccccc')

        # 提示
        ax.text(0.5, 0.07,
                f'💡 相关系数 = 各因子与碳酸锂主力合约结算价的 Pearson 相关系数',
                ha='center', va='center', fontsize=9, color='#666666', style='italic')
        ax.text(0.5, 0.03,
                f'📄 使用"文件 → 导出全部因子相关性"可下载完整 {feature_count} 个因子表格',
                ha='center', va='center', fontsize=9, color='#888888')

        self.figure.tight_layout()
        self.canvas.draw()
        self.statusBar.showMessage(f"基本面量化分析完成 - 共 {feature_count} 个因子，显示前 20 个")

    def onFundamentalError(self, error_msg):
        QMessageBox.critical(self, "错误", f"基本面量化分析失败：{error_msg}")
        self.statusBar.showMessage("分析失败")

    # ==================== 因子分析 ====================
    def initFactorInputs(self):
        if self.current_file is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        for widget in self.factor_scroll_widget.findChildren(QWidget):
            widget.deleteLater()
        self.factor_input_widgets = {}

        try:
            fq = FundamentalQuant(self.current_file)
            top_features = fq.top10_features
            default_vals = fq.get_default_factor_values()

            self.factor_top_features = top_features
            self.factor_default_values = default_vals

            for feature in top_features:
                layout = QHBoxLayout()
                label = QLabel(feature[:25])
                label.setMinimumWidth(150)
                label.setToolTip(feature)
                layout.addWidget(label)

                input_box = QLineEdit()
                mean_val = default_vals.get(feature, 0)
                input_box.setText(f"{mean_val:.4f}")
                input_box.setPlaceholderText("输入数值")
                layout.addWidget(input_box)

                self.factor_input_widgets[feature] = input_box
                self.factor_scroll_layout.addLayout(layout)

            self.factor_scroll_layout.addStretch()

            if not self.factor_initial_run:
                self.factor_initial_run = True
                self.factor_status_label.setText(f"💡 默认值为最新两月均值，正在自动预测...")
                self.statusBar.showMessage("正在自动进行因子分析预测...")
                QTimer.singleShot(300, self._auto_run_factor_analysis)
            else:
                self.factor_status_label.setText("💡 默认值为最新两月均值，可直接修改")

        except Exception as e:
            import traceback
            QMessageBox.warning(self, "错误", f"初始化因子分析失败：{str(e)}\n{traceback.format_exc()}")

    def _auto_run_factor_analysis(self):
        if self.current_file is None:
            return
        self.fundamental_thread = FactorAnalysisThread(self.current_file, custom_values=None)
        self.fundamental_thread.finished.connect(self.onFactorComplete)
        self.fundamental_thread.error.connect(self.onFundamentalError)
        self.fundamental_thread.start()

    def resetFactorInputs(self):
        if not self.factor_input_widgets:
            return
        for feature, widget in self.factor_input_widgets.items():
            if feature in self.factor_default_values:
                widget.setText(f"{self.factor_default_values[feature]:.4f}")
        self.factor_status_label.setText("✅ 已重置为最新两月均值")
        self.factor_status_label.setStyleSheet("color: #4CAF50; padding: 5px;")

    def runFactorAnalysis(self):
        if self.current_file is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        modified_features = {}
        for feature, widget in self.factor_input_widgets.items():
            try:
                val = float(widget.text().strip())
                modified_features[feature] = val
            except ValueError:
                QMessageBox.warning(self, "错误", f"请输入有效的数值: {feature}")
                return

        self.factor_status_label.setText("🔄 正在运行因子分析...")
        self.factor_status_label.setStyleSheet("color: #2196F3; padding: 5px;")
        self.statusBar.showMessage("正在进行因子分析...")

        self.fundamental_thread = FactorAnalysisThread(
            self.current_file, custom_values=modified_features
        )
        self.fundamental_thread.finished.connect(self.onFactorComplete)
        self.fundamental_thread.error.connect(self.onFundamentalError)
        self.fundamental_thread.start()

    def onFactorComplete(self, result):
        self.factor_result = result
        r = result['result']
        top_features = result.get('top_features', [])
        latest_month = result.get('latest_month', '')
        all_feature_count = result.get('all_feature_count', 0)
        correlations = result.get('correlations', [])

        self.figure.clear()
        gs = self.figure.add_gridspec(3, 1, height_ratios=[1.2, 1.5, 0.9])

        ax_table = self.figure.add_subplot(gs[0])
        ax_table.axis('off')

        table_data = [
            ['预测结果', '多头概率', '空头概率', '模型准确率', '训练样本', '使用因子数'],
            [r['prediction'], f"{r['prob_bull']:.1%}", f"{r['prob_bear']:.1%}",
             f"{r['accuracy']:.1%}", str(r['total_samples']), str(r['feature_count'])],
        ]

        table = ax_table.table(cellText=table_data, loc='center', cellLoc='center',
                               colWidths=[0.15, 0.15, 0.15, 0.15, 0.15, 0.15],
                               bbox=[0.05, 0.15, 0.90, 0.60])
        table.auto_set_font_size(False)
        table.set_fontsize(12)

        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_facecolor('#2196F3')
                cell.set_text_props(color='white', fontweight='bold')
            elif i == 1:
                if r['prediction'] == '多头':
                    cell.set_facecolor('#4CAF50')
                    cell.set_text_props(color='white', fontweight='bold')
                else:
                    cell.set_facecolor('#f44336')
                    cell.set_text_props(color='white', fontweight='bold')
            cell.set_edgecolor('#cccccc')

        ax_table.text(0.5, 0.95, '🧩 因子分析预测结果', ha='center', va='center',
                      fontsize=16, fontweight='bold')
        ax_table.text(0.5, 0.85,
                      f"数据区间: 截至 {latest_month}  |  输入方式: {r['test_label']}  |  全部因子: {all_feature_count} 个",
                      ha='center', va='center', fontsize=9, color='gray')

        suggestion = '💡 建议：当前因子组合下，预测价格上涨，可考虑多头配置' if r['prediction'] == '多头' \
            else '💡 建议：当前因子组合下，预测价格下跌，可考虑空头配置或套保'
        ax_table.text(0.5, 0.05, suggestion, ha='center', va='center',
                      fontsize=12, fontweight='bold', color='#2196F3')

        ax_top = self.figure.add_subplot(gs[1])
        ax_top.axis('off')

        top_table_data = [['排名', '因子名称', '相关系数', '方向', '当前输入值']]
        for i, feat in enumerate(top_features, 1):
            corr_val = 0
            direction = '正相关'
            for item in correlations:
                if item['特征'] == feat:
                    corr_val = item['相关系数']
                    direction = item['方向']
                    break
            input_val = "默认"
            if feat in self.factor_input_widgets:
                input_val = self.factor_input_widgets[feat].text()

            top_table_data.append([
                str(i),
                feat[:42],
                f"{corr_val:+.4f}",
                direction,
                input_val
            ])

        top_table = ax_top.table(cellText=top_table_data, loc='center', cellLoc='left',
                                  colWidths=[0.06, 0.50, 0.14, 0.12, 0.18],
                                  bbox=[0.03, 0.10, 0.94, 0.80])
        top_table.auto_set_font_size(False)
        top_table.set_fontsize(9)

        for (i, j), cell in top_table.get_celld().items():
            if i == 0:
                cell.set_facecolor('#FF9800')
                cell.set_text_props(color='white', fontweight='bold')
            else:
                if j == 3:
                    text = cell.get_text().get_text()
                    if '正相关' in text:
                        cell.set_facecolor('#E8F5E9')
                    elif '负相关' in text:
                        cell.set_facecolor('#FFEBEE')
                elif i % 2 == 0:
                    cell.set_facecolor('#f5f5f5')
            cell.set_edgecolor('#cccccc')

        ax_top.text(0.5, 0.95, f'进入 KNN 的 Top 10 因子',
                    ha='center', va='center', fontsize=11, fontweight='bold')

        ax_detail = self.figure.add_subplot(gs[2])
        ax_detail.axis('off')

        neighbor_labels = r['neighbor_labels']
        label_counts = {'多头': neighbor_labels.count('多头'), '空头': neighbor_labels.count('空头')}
        counts = [label_counts.get('多头', 0), label_counts.get('空头', 0)]

        bars = ax_detail.bar(['多头', '空头'], counts, color=['#4CAF50', '#f44336'],
                             alpha=0.7, edgecolor='black', linewidth=0.5, width=0.4)
        ax_detail.set_xlabel('方向', fontsize=9)
        ax_detail.set_ylabel('相似月份数量', fontsize=9)
        ax_detail.set_title(f'最近相似月份方向分布  ({", ".join(r["neighbor_quarters"])})',
                            fontsize=10, fontweight='bold')
        ax_detail.grid(True, alpha=0.3, axis='y')
        for bar, count in zip(bars, counts):
            ax_detail.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                           str(count), ha='center', va='bottom', fontsize=10, fontweight='bold')

        self.figure.tight_layout()
        self.canvas.draw()
        self.factor_status_label.setText("✅ 因子分析完成")
        self.factor_status_label.setStyleSheet("color: #4CAF50; padding: 5px;")
        self.statusBar.showMessage("因子分析完成")

    def showWelcomeMessage(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.6, '🔋 碳酸锂数据分析工具 v2.0', ha='center', va='center',
                fontsize=24, fontweight='bold')
        ax.text(0.5, 0.4, '请点击左侧"加载Excel文件"按钮导入数据', ha='center', va='center',
                fontsize=14, color='gray')
        ax.text(0.5, 0.3, '支持功能：历史分位 | 统计信息 | 传导量化 | 基本面量化 | 因子分析',
                ha='center', va='center', fontsize=12, color='gray')
        ax.axis('off')
        self.canvas.draw()

    def resetView(self):
        if self.current_mode == 'history':
            self.plotHistoryCharts()
        elif self.current_mode == 'stats':
            self.plotStatsCharts()
        elif self.current_mode == 'conduction':
            if all(v is not None for v in self.conduction_inputs.values()):
                self.updateConductionDisplay()
            else:
                self.showConductionWelcome()
        elif self.current_mode == 'fundamental':
            if self.correlation_result:
                self.onFundamentalComplete(self.correlation_result)
            else:
                self.runFundamentalQuant()
        elif self.current_mode == 'factor':
            self.initFactorInputs()
        self.statusBar.showMessage("视图已重置")

    def exportStats(self):
        if not self.all_stats:
            QMessageBox.warning(self, "警告", "没有统计数据可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存统计表格", "统计结果汇总.xlsx",
            "Excel文件 (*.xlsx);;CSV文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            table_data = []
            for name, stats in self.all_stats.items():
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
                    '近一月支撑位': stats['month_support'] if stats['month_support'] is not None else '未找到',
                    '近一月阻力位': stats['month_resistance'] if stats['month_resistance'] is not None else '未找到',
                    '近一年支撑位': stats['year_support'] if stats['year_support'] is not None else '未找到',
                    '近一年阻力位': stats['year_resistance'] if stats['year_resistance'] is not None else '未找到',
                }
                table_data.append(row)

            df = pd.DataFrame(table_data)
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                if not file_path.endswith('.xlsx'):
                    file_path += '.xlsx'
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='统计汇总', index=False)

            QMessageBox.information(self, "成功", f"统计表格已导出到：\n{file_path}")
            self.statusBar.showMessage(f"表格已导出: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{str(e)}")

    def exportAllCorrelations(self):
        """导出全部因子相关性"""
        if self.current_file is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存因子相关性表格", "因子相关性分析.xlsx",
            "Excel文件 (*.xlsx);;CSV文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            fq = FundamentalQuant(self.current_file)
            corr_df = fq.get_full_correlation_table()

            if file_path.endswith('.csv'):
                corr_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                if not file_path.endswith('.xlsx'):
                    file_path += '.xlsx'
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    corr_df.to_excel(writer, sheet_name='因子相关性', index=False)

            QMessageBox.information(self, "成功",
                                    f"因子相关性表格已导出到：\n{file_path}\n\n共导出 {len(corr_df)} 个因子")
            self.statusBar.showMessage(f"因子相关性表格已导出: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{str(e)}")

    def showAbout(self):
        QMessageBox.about(
            self, "关于",
            "🔋 碳酸锂数据分析工具 v2.0\n\n"
            "功能特性：\n"
            "• 历史分位分析 - 价格走势与分位数图\n"
            "• 统计信息 - 完整统计指标\n"
            "• 传导量化 - CDI偏离度监控\n"
            "• 基本面量化 - 全部因子相关性分析\n"
            "• 因子分析 - Top 10 因子KNN预测（可自定义）\n"
            "• 因子相关性导出 - 导出全部因子相关性\n\n"
            "技术支持：数据来源于SMM"
        )

    def closeEvent(self, event):
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    window = LithiumAnalyzer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()