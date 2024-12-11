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
    QCheckBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os

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

    def __init__(self, username: str, password: str, search_text: str = None, 
                 status_filters: list = None):
        super().__init__()
        self.username = username
        self.password = password
        self.search_text = search_text
        self.status_filters = status_filters or ["開課中"]
        self.login_manager = None
        self.parser = None
        self.stop_flag = False
        
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
                status_filters=self.status_filters
            )
            
            self.parser.data_ready = self.data_ready

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
        """停止爬蟲"""
        self.stop_flag = True
        if self.parser:
            self.parser.stop_crawling = True
        if self.login_manager:
            self.login_manager.close()

class MainWindow(QMainWindow):
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
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 登入區域
        login_group = QWidget()
        login_layout = QHBoxLayout(login_group)
        
        username_label = QLabel("帳號:")
        self.username_input = QLineEdit()
        login_layout.addWidget(username_label)
        login_layout.addWidget(self.username_input)
        
        password_label = QLabel("密碼:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        login_layout.addWidget(password_label)
        login_layout.addWidget(self.password_input)
        
        # 搜尋區域
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
        
        # 按鈕區域
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
        
        # 日誌視窗
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 課程列表
        self.course_table = QTableWidget()
        self.course_table.setColumnCount(8)
        self.course_table.setHorizontalHeaderLabels([
            '課程狀態',
            '課程名稱', 
            '選修人數(台灣)', 
            '選修人數(中國大陸)',
            '選修人數(其他)',
            '通過人數(台灣)',
            '通過人數(中國大陸)',
            '通過人數(其他)'
        ])
        self.course_table.horizontalHeader().setStretchLastSection(True)
        self.course_table.verticalHeader().setVisible(False)
        self.course_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.course_table)

    def setup_window_icon(self):
        """設定視窗圖示"""
        icon_path = ResourceUtils.get_resource_path('icon.ico')
        if icon_path:
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)

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

        self._update_ui_state(is_crawling=True)
        self.config.save_config(username, password)
        
        self.log_message("開始爬取程序...")
        self.crawler_thread = CrawlerThread(
            username, 
            password, 
            search_text,
            status_filters=status_filters
        )

        self.crawler_thread.progress.connect(self.log_message)
        self.crawler_thread.finished.connect(self.handle_crawler_result)
        self.crawler_thread.data_ready.connect(self.update_course_table)

        self.crawler_thread.start()

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
                    # 設定課程狀態
                    self.course_table.setItem(row, 0, QTableWidgetItem(course.get('status', '')))
                    # 設定課程名稱
                    self.course_table.setItem(row, 1, QTableWidgetItem(course['name']))
                    
                    # 設定選修和通過人數資料
                    if 'stats' in course and course['stats']:
                        stats = course['stats']

                        # 選修人數
                        self.course_table.setItem(row, 2, QTableWidgetItem(str(stats['選修人數']['台灣'])))
                        self.course_table.setItem(row, 3, QTableWidgetItem(str(stats['選修人數']['中國大陸'])))
                        self.course_table.setItem(row, 4, QTableWidgetItem(str(stats['選修人數']['其他'])))
                        
                        # 通過人數
                        self.course_table.setItem(row, 5, QTableWidgetItem(str(stats['通過人數']['台灣'])))
                        self.course_table.setItem(row, 6, QTableWidgetItem(str(stats['通過人數']['中國大陸'])))
                        self.course_table.setItem(row, 7, QTableWidgetItem(str(stats['通過人數']['其他'])))
                    else:
                        # 如果沒有統計資料，填入空值
                        for col in range(2, 8):
                            self.course_table.setItem(row, col, QTableWidgetItem('0'))
                        self.log_message(f"第 {row + 1} 筆課程缺少統計資料")
                    
                    # 設定每個儲存格的對齊方式
                    for col in range(8):
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
            for col in range(2, 8):  # 數字欄位最小寬度
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
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.log_message("正在停止爬蟲...")
            self.crawler_thread.stop()
            self.crawler_thread.wait()
            self.crawler_thread = None
            if hasattr(self, 'course_table') and self.courses:
                self.update_course_table(self.courses)
            self.crawler_thread = None
            self._update_ui_state(is_crawling=False)
    
    def export_report(self):
        """匯出報表"""
        self.log_message("開始匯出報表...")
        
        exporter = CourseExporter(self.course_table)
        exporter.export_to_excel()
    
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
        self.export_button.setEnabled(not is_crawling)

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