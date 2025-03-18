from PyQt6.QtWidgets import (
    QMainWindow, 
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QAbstractItemView,
    QTextEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QDateEdit,
    QApplication,
    QProgressBar
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QDate, QTimer
import os
import psutil
from datetime import datetime

from src.crawler.login import EwantLogin
from src.crawler.parser import CourseParser
from src.crawler.export import CourseExporter
from src.utils.config import Config
from src.utils.resource_utils import ResourceUtils

class CrawlerThread(QThread):
    """處理爬蟲的工作執行緒"""
    finished = pyqtSignal(bool, str)   # 信號：(是否成功, 訊息)
    progress = pyqtSignal(str)         # 信號：進度訊息
    data_ready = pyqtSignal(list)      # 信號：爬取到的資料
    progress_percent = pyqtSignal(int) # 信號：進度百分比
    time_remaining = pyqtSignal(str)   # 信號：剩餘時間

    def __init__(self, username: str, password: str, search_text: str = None, 
                 status_filters: list = None, start_date=None, end_date=None):
        super().__init__()
        self.username = username
        self.password = password
        self.search_text = search_text
        self.status_filters = status_filters or ["開課中"]
        self.start_date = start_date
        self.end_date = end_date
        self.login_manager = None
        self.parser = None
        self.stop_flag = False
        self.cleanup_timeout = 3  # 設定清理資源的最大等待時間（秒）
        
    def run(self):
        try:
            # 執行登入
            self.progress.emit("初始化登入...")
            self.login_manager = EwantLogin(headless=True)
            
            self.progress.emit("開始登入...")
            success, message = self.login_manager.login(self.username, self.password)
            
            if not success:
                self.finished.emit(False, f"登入失敗：{message}")
                return

            # 開始爬取資料
            self.progress.emit("開始爬取課程資料...")
            self.parser = CourseParser(
                self.login_manager.get_driver(), 
                progress=self.progress,
                search_text=self.search_text,
                status_filters=self.status_filters,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            self.parser.data_ready = self.data_ready
            self.parser.progress_percent = self.progress_percent
            self.parser.time_remaining = self.time_remaining

            try:
                # 執行爬蟲並獲取結果
                courses = self.parser.process_all_courses()

                if courses:
                    # 直接發送完整的課程資料
                    self.data_ready.emit(courses)
                    self.finished.emit(True, "爬取完成")
                else:
                    self.finished.emit(False, "未取得任何課程資料")
                
            except Exception as e:
                self.finished.emit(False, f"爬取過程發生錯誤：{str(e)}")
            
            finally:
                # 確保總是清理資源
                if self.login_manager:
                    self.login_manager.close()
                
        except Exception as e:
            self.finished.emit(False, f"執行過程發生錯誤：{str(e)}")
        
    def stop(self):
        """停止爬蟲並快速釋放資源"""
        self.stop_flag = True
        
        if self.parser:
            self.parser.stop_crawling = True
            self.parser = None
        
        if self.login_manager and self.login_manager.driver:
            try:
                # 先嘗試透過WebDriver關閉
                self.login_manager.driver.quit()
            except:
                pass
            
            # 強制終止所有Chrome進程 (僅用於非生產環境)
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    if 'chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower():
                        try:
                            proc.terminate()  # 嘗試優雅終止
                        except:
                            pass
            except:
                pass
                
            self.login_manager = None

class StopWorker(QObject):
    """停止爬蟲的工作執行緒"""
    finished = pyqtSignal()
    
    def __init__(self, crawler_thread):
        super().__init__()
        self.crawler_thread = crawler_thread
    
    def run(self):
        try:
            if self.crawler_thread:
                self.crawler_thread.stop()
                self.crawler_thread.wait()
        except Exception as e:
            print(f"停止爬蟲時發生錯誤: {str(e)}")
        finally:
            self.finished.emit()

class MainWindow(QMainWindow):
    """主視窗"""
    # 信號
    stop_finished = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setWindowTitle("課程資料爬蟲工具")
        self.setMinimumSize(800, 600)
        self.setup_window_icon()
        self.init_ui()
        self.load_config()
        self.crawler_thread = None
        self.last_valid_row_count = 0
        self.courses = []
        self.is_stopping = False
        self.showMaximized()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # ===帳號輸入區域===
        login_group = QWidget()
        login_layout = QHBoxLayout(login_group)
        
        username_label = QLabel("帳號:")
        self.username_input = QLineEdit()
        login_layout.addWidget(username_label)
        login_layout.addWidget(self.username_input)
        
        # ===密碼輸入區域===
        password_label = QLabel("密碼:")
        password_container = QWidget()
        password_layout = QHBoxLayout(password_container)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(2)
        
        # 密碼輸入框
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        # 檢視密碼按鈕
        self.toggle_password_btn = QPushButton("👁")
        self.toggle_password_btn.setFixedWidth(25)
        self.toggle_password_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 0px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.toggle_password_btn.clicked.connect(self.toggle_password_visibility)
        self.toggle_password_btn.setToolTip("顯示密碼")

        # 將元件加入密碼容器
        password_layout.addWidget(self.password_input)
        password_layout.addWidget(self.toggle_password_btn)
        
        login_layout.addWidget(password_label)
        login_layout.addWidget(password_container)

        # ===搜尋區域===
        search_group = QWidget()
        search_layout = QHBoxLayout(search_group)
        
        search_label = QLabel("搜尋課程:")
        self.search_input = QLineEdit()
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)

        # 在搜尋區域加入課程狀態選項
        status_group = QWidget()
        status_layout = QHBoxLayout(status_group)
        
        status_label = QLabel("課程狀態:")
        status_layout.addWidget(status_label)
        
        self.ongoing_checkbox = QCheckBox("開課中")
        self.ongoing_checkbox.setChecked(True)  # 預設勾選
        status_layout.addWidget(self.ongoing_checkbox)
        
        self.upcoming_checkbox = QCheckBox("即將開課")
        self.upcoming_checkbox.setChecked(False)
        status_layout.addWidget(self.upcoming_checkbox)
        
        self.finished_checkbox = QCheckBox("已結束")
        self.finished_checkbox.setChecked(False)
        status_layout.addWidget(self.finished_checkbox)
        
        status_layout.addStretch()  # 增加彈性空間
        
        layout.addWidget(login_group)
        layout.addWidget(search_group)
        layout.addWidget(status_group)
        
        # ===日期範圍選擇區域===
        date_group = QWidget()
        date_layout = QHBoxLayout(date_group)

        date_layout.addWidget(QLabel("開課日期範圍:"))

        # 計算本月第一天和最後一天的日期
        current_date = QDate.currentDate()
        first_day = QDate(current_date.year(), current_date.month(), 1)
        last_day = QDate(current_date.year(), current_date.month(), current_date.daysInMonth())

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(first_day)  # 設定為本月第一天
        self.start_date.setDisplayFormat("yyyy-MM-dd")  # 設定顯示格式
        date_layout.addWidget(self.start_date)

        date_layout.addWidget(QLabel("至"))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(last_day)  # 設定為本月最後一天
        self.end_date.setDisplayFormat("yyyy-MM-dd")  # 設定顯示格式
        date_layout.addWidget(self.end_date)

        # 日期範圍的啟用/禁用選項
        self.enable_date_filter = QCheckBox("啟用日期過濾")
        self.enable_date_filter.setChecked(False)
        self.enable_date_filter.stateChanged.connect(self.toggle_date_filter)
        date_layout.addWidget(self.enable_date_filter)

        # 清除日期按鈕
        self.clear_date_btn = QPushButton("重設日期")
        self.clear_date_btn.clicked.connect(self.reset_date_range)
        date_layout.addWidget(self.clear_date_btn)

        date_layout.addStretch()

        # 將日期選擇區域加入主布局
        layout.addWidget(date_group)

        # ===按鈕區域===
        button_group = QWidget()
        button_layout = QHBoxLayout(button_group)

        self.start_button = QPushButton("開始爬取")
        self.start_button.clicked.connect(self.start_crawling)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止爬取")
        self.stop_button.clicked.connect(self.stop_crawling)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        self.export_button = QPushButton("匯出報表")
        self.export_button.clicked.connect(self.export_report)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)

        layout.addWidget(button_group)
        
        # ===日誌視窗===
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 添加進度條和剩餘時間的容器
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # 設置進度條樣式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #E0E0E0;
                text-align: center;
                color: #333333;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8FE589, stop:1 #00A651);
            }
        """)

        progress_layout.addWidget(self.progress_bar)
        
        # 添加剩餘時間標籤
        self.remaining_time_label = QLabel("剩餘時間: --:--")
        progress_layout.addWidget(self.remaining_time_label)
        
        layout.addWidget(progress_container)

        # 課程列表
        self.course_table = QTableWidget()
        self.course_table.setColumnCount(20)
        self.course_table.setHorizontalHeaderLabels([
            '課程狀態',
            '課程名稱',
            '開始時間',
            '結束時間', 
            '選修人數(台灣)',
            '選修人數(中國大陸)',
            '選修人數(其他)',
            '通過人數(台灣)',
            '通過人數(中國大陸)',
            '通過人數(其他)',
            '影片瀏覽次數(台灣)',
            '影片瀏覽次數(中國大陸)',
            '影片瀏覽次數(其他)',
            '作業測驗作答次數(台灣)',
            '作業測驗作答次數(中國大陸)',
            '作業測驗作答次數(其他)',
            '講義參考資料瀏覽次數(台灣)',
            '講義參考資料瀏覽次數(中國大陸)',
            '講義參考資料瀏覽次數(其他)',
            '討論次數'
        ])

        # 設定表格屬性
        self.course_table.horizontalHeader().setStretchLastSection(True)
        self.course_table.verticalHeader().setVisible(False)
        self.course_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # 設定表格的水平捲動
        self.course_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.course_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        layout.addWidget(self.course_table)

    def setup_window_icon(self):
        """設定視窗圖示"""
        icon_path = ResourceUtils.get_resource_path('icon.ico')
        if (icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
    
    def toggle_password_visibility(self):
        """切換密碼可見性"""
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_password_btn.setText("🔒")  # 改用鎖定符號
            self.toggle_password_btn.setToolTip("隱藏密碼")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_password_btn.setText("👁")  # 改用眼睛符號
            self.toggle_password_btn.setToolTip("顯示密碼")
    
    def load_config(self):
        """載入設定"""
        self.config = Config()
        saved_config = self.config.load_config()
        self.username_input.setText(saved_config.get('username', ''))
        self.password_input.setText(saved_config.get('password', ''))

    def start_crawling(self):
        """開始爬蟲"""
        # 取得使用者輸入、密碼、搜尋課程
        username = self.username_input.text()
        password = self.password_input.text()
        search_text = self.search_input.text()
        if not username or not password:
                    QMessageBox.warning(self, "警告", "請輸入帳號和密碼")
                    return
        
        # 清空課程表格
        self.courses = []
        self.last_valid_row_count = 0

        # 檢查是否至少選擇一個狀態
        status_filters = []
        if self.ongoing_checkbox.isChecked():
            status_filters.append("開課中")
        if self.upcoming_checkbox.isChecked():
            status_filters.append("即將開課")
        if self.finished_checkbox.isChecked():
            status_filters.append("已結束")
        if not status_filters:
            QMessageBox.warning(self, "警告", "請至少選擇一種課程狀態")
            return

        # 檢查日期範圍
        start_date = None
        end_date = None

        if self.enable_date_filter.isChecked():
            if self.start_date.date() <= self.end_date.date():
                start_date = datetime.combine(self.start_date.date().toPyDate(), datetime.min.time())
                end_date = datetime.combine(self.end_date.date().toPyDate(), datetime.max.time())
                self.log_message(f"篩選日期範圍: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
            else:
                QMessageBox.warning(self, "警告", "結束日期必須大於等於開始日期")
                return
        else:
            self.log_message("未啟用日期過濾")

        self._update_ui_state(is_crawling=True)
        self.config.save_config(username, password)
        
        self.log_message("開始爬取程序...")
        self.crawler_thread = CrawlerThread(
            username, 
            password, 
            search_text,
            status_filters=status_filters,
            start_date=start_date,
            end_date=end_date
        )

        self.crawler_thread.progress.connect(self.log_message)
        self.crawler_thread.progress_percent.connect(self.update_progress)
        self.crawler_thread.time_remaining.connect(self.update_remaining_time)
        self.crawler_thread.finished.connect(self.handle_crawler_result)
        self.crawler_thread.data_ready.connect(self.update_course_table)

        # 重置進度條和剩餘時間
        self.progress_bar.setValue(0)
        self.remaining_time_label.setText("剩餘時間: --:--")
        self.progress_bar.repaint()
        self.remaining_time_label.repaint()
        
        self.crawler_thread.start()

    def toggle_date_filter(self, state):
        """切換日期過濾器啟用狀態"""
        # 不使用state參數的比較，改為直接取得勾選框的當前狀態
        enabled = self.enable_date_filter.isChecked()
        
        # 設置控件啟用狀態
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)
        self.clear_date_btn.setEnabled(enabled)
        
        # 強制更新UI
        QApplication.processEvents()
        
        # 在日誌中輸出實際狀態，幫助診斷
        self.log_message(f"日期過濾已{'啟用' if enabled else '停用'}")

    def reset_date_range(self):
        """重設日期範圍到本月的第一天和最後一天"""
        currentDate = QDate.currentDate()
        first_day = QDate(currentDate.year(), currentDate.month(), 1)
        last_day = QDate(currentDate.year(), currentDate.month(), currentDate.daysInMonth())
        
        self.start_date.setDate(first_day)
        self.end_date.setDate(last_day)
        self.start_date.clearFocus()
        self.end_date.clearFocus()

    def clear_date_range(self):
        """清除日期範圍"""
        self.start_date.setDate(QDate.currentDate())
        self.end_date.setDate(QDate.currentDate())
        self.start_date.clearFocus()
        self.end_date.clearFocus()

    def _create_table_item(self, value, is_numeric=False):
        """建立表格項目"""
        if is_numeric:
            try:
                # 移除任何非數字字元並轉換為整數
                number = int(''.join(filter(str.isdigit, str(value))))
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, number)
            except (ValueError, TypeError):
                item = QTableWidgetItem('0')
                item.setData(Qt.ItemDataRole.DisplayRole, 0)
        else:
            item = QTableWidgetItem(str(value))
        
        return item

    def update_course_table(self, courses):
        """更新課程表格"""
        try:
            # 獲取最後有效的資料列
            if self.crawler_thread and not self.crawler_thread.stop_flag:
                self.last_valid_row_count = len(courses)
                self.courses = courses
            else:
                courses = courses[:self.last_valid_row_count]
            
            self.course_table.setRowCount(len(courses))
            
            for row, course in enumerate(courses):
                try:
                    # 設定基本資訊
                    self.course_table.setItem(row, 0, self._create_table_item(course.get('status', '')))
                    self.course_table.setItem(row, 1, self._create_table_item(course['name']))
                    self.course_table.setItem(row, 2, self._create_table_item(course.get('start_time', '')))
                    self.course_table.setItem(row, 3, self._create_table_item(course.get('end_time', '')))
                    
                    # 設定選修和通過人數資料
                    if 'stats' in course and course['stats']:
                        stats = course['stats']

                        numeric_items = [
                            stats['選修人數']['台灣'],
                            stats['選修人數']['中國大陸'],
                            stats['選修人數']['其他'],
                            stats['通過人數']['台灣'],
                            stats['通過人數']['中國大陸'],
                            stats['通過人數']['其他'],
                            stats.get('影片瀏覽次數', {}).get('台灣', 0),
                            stats.get('影片瀏覽次數', {}).get('中國大陸', 0),
                            stats.get('影片瀏覽次數', {}).get('其他', 0),
                            stats.get('作業測驗作答次數', {}).get('台灣', 0),
                            stats.get('作業測驗作答次數', {}).get('中國大陸', 0),
                            stats.get('作業測驗作答次數', {}).get('其他', 0),
                            stats.get('講義參考資料瀏覽次數', {}).get('台灣', 0),
                            stats.get('講義參考資料瀏覽次數', {}).get('中國大陸', 0),
                            stats.get('講義參考資料瀏覽次數', {}).get('其他', 0),
                            stats.get('討論次數', 0)
                        ]

                        # 設定所有數字欄位
                        for col, value in enumerate(numeric_items, start=4):
                            item = self._create_table_item(value, is_numeric=True)
                            # 設定對齊方式為靠右
                            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            self.course_table.setItem(row, col, item)
                    
                    else:
                        # 如果沒有統計資料，填入空值
                        for col in range(4, 20):
                            self.course_table.setItem(row, col, QTableWidgetItem('0'))
                        self.log_message(f"第 {row + 1} 筆課程缺少統計資料")
                    
                    # 設定每個儲存格的對齊方式
                    for col in range(20):
                        item = self.course_table.item(row, col)
                        if item:
                            # 課程名稱靠左，其他靠右對齊
                            if col == 1:  # 課程名稱
                                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                            else:  # 其他欄位
                                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        
                except Exception as e:
                    self.log_message(f"更新第 {row + 1} 筆資料時發生錯誤：{str(e)}")
            
            # 調整欄寬並滾動到最下方
            self.course_table.resizeColumnsToContents()
            self.course_table.scrollToBottom()
            self.log_message(f"已更新第{len(courses)}筆資料進入表格")

            # 設定最小欄寬
            min_width = 80
            for col in range(2, 20):
                if self.course_table.columnWidth(col) < min_width:
                    self.course_table.setColumnWidth(col, min_width)
            
            # 課程名稱欄位最小寬度
            name_col_min_width = 200
            if self.course_table.columnWidth(1) < name_col_min_width:
                self.course_table.setColumnWidth(1, name_col_min_width)
            
        except Exception as e:
            self.log_message(f"更新表格時發生錯誤：{str(e)}")
            
        # 更新匯出按鈕狀態
        self.export_button.setEnabled(self.course_table.rowCount() > 0)

    def stop_crawling(self):
        """停止爬取"""
        if not self.is_stopping and self.crawler_thread and self.crawler_thread.isRunning():
            self.is_stopping = True
            self.log_message("正在停止爬蟲...")
            self.stop_button.setEnabled(False)
            
            # 僅設置停止標誌，不等待
            if self.crawler_thread:
                self.crawler_thread.stop()
                
                # 創建一個計時器，定期檢查線程是否結束
                self.check_timer = QTimer()
                self.check_timer.timeout.connect(self.check_thread_stopped)
                self.check_timer.start(500)  # 每500毫秒檢查一次

    def check_thread_stopped(self):
        """檢查爬蟲線程是否已停止"""
        if not self.crawler_thread or not self.crawler_thread.isRunning():
            self.check_timer.stop()
            self.is_stopping = False
            self.crawler_thread = None
            if hasattr(self, 'course_table') and self.courses:
                self.update_course_table(self.courses)
            self._update_ui_state(is_crawling=False)
            self.log_message("爬蟲已停止")
    
    def on_stop_finished(self):
        """停止完成後的處理"""
        self.is_stopping = False
        self.crawler_thread = None
        if hasattr(self, 'course_table') and self.courses:
            self.update_course_table(self.courses)
        self._update_ui_state(is_crawling=False)
        self.log_message("爬蟲已停止")
    
    def export_report(self):
        """匯出報表"""
        self.log_message("開始匯出報表...")
        
        # 生成過濾資訊字串
        filter_info = None
        if self.course_table.rowCount() > 0:
            filter_info = f"{self.course_table.rowCount()}筆資料"
        
        # 如果有日期過濾
        if self.enable_date_filter.isChecked():
            start_date_str = self.start_date.date().toString("yyyyMMdd")
            end_date_str = self.end_date.date().toString("yyyyMMdd")
            if filter_info:
                filter_info += f"_{start_date_str}到{end_date_str}"
            else:
                filter_info = f"{start_date_str}到{end_date_str}"
        
        exporter = CourseExporter(self.course_table)
        exporter.export_to_excel(filter_info)
    
    def log_message(self, message):
        """添加日誌訊息"""
        self.log_text.append(message)
        # 自動滾動到最下方
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def _update_ui_state(self, is_crawling: bool):
        """更新UI狀態"""
        self.start_button.setEnabled(not is_crawling)
        self.stop_button.setEnabled(is_crawling)
        self.username_input.setEnabled(not is_crawling)
        self.password_input.setEnabled(not is_crawling)
        self.export_button.setEnabled(not is_crawling and self.course_table.rowCount() > 0)

    def handle_crawler_result(self, success: bool, message: str):
        """處理爬蟲結果"""
        self._update_ui_state(is_crawling=False)
        
        if success:
            self.log_message("爬取完成！")
            self.export_button.setEnabled(True)
        else:
            self.log_message(f"爬取失敗：{message}")
            QMessageBox.critical(self, "錯誤", f"爬取失敗：{message}")

        # 關閉瀏覽器
        if self.crawler_thread and self.crawler_thread.login_manager:
            self.crawler_thread.login_manager.close()

    def handle_crawler_data(self, data: list):
        """處理爬取到的資料"""
        self.update_course_table(data)

    def closeEvent(self, event):
        """視窗關閉事件"""
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.stop_crawling()
            self.crawler_thread.wait()
        event.accept()
    
    def _setup_date_filter(self):
        self.ui.checkBox_date.stateChanged.connect(self._on_date_filter_changed)
        
    def _on_date_filter_changed(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        self.ui.dateEdit_start.setEnabled(not is_checked)
        self.ui.dateEdit_end.setEnabled(not is_checked)
        if is_checked:
            # 當勾選時，儲存目前的日期值並鎖定
            self.start_date = self.ui.dateEdit_start.date()
            self.end_date = self.ui.dateEdit_end.date()

    def update_progress(self, percent):
        """更新進度條"""
        try:
            if percent >= 0 and percent <= 100:
                self.progress_bar.setValue(percent)
                # 強制立即更新UI
                self.progress_bar.repaint()
            QApplication.processEvents()
        except Exception as e:
            print(f"更新進度條時發生錯誤：{str(e)}")

    def update_remaining_time(self, time_text):
        """更新剩餘時間顯示"""
        try:
            self.remaining_time_label.setText(f"剩餘時間: {time_text}")
            # 強制立即更新UI
            self.remaining_time_label.repaint()
            QApplication.processEvents()
        except Exception as e:
            print(f"更新剩餘時間時發生錯誤：{str(e)}")