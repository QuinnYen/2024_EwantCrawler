from PyQt6.QtWidgets import (
    QMainWindow, 
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QMessageBox,
    QListWidget
)
import time
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from src.crawler.login import EwantLogin
from src.crawler.parser import CourseParser
from src.utils.config import Config

class CrawlerThread(QThread):
   """處理爬蟲的工作執行緒"""
   finished = pyqtSignal(bool, str)   # 信號：(是否成功, 訊息)
   progress = pyqtSignal(str)         # 信號：進度訊息
   data_ready = pyqtSignal(list)      # 信號：爬取到的資料

   def __init__(self, username: str, password: str, search_text: str = None):
       super().__init__()
       self.username = username
       self.password = password
       self.search_text = search_text
       self.login_manager = None
       self.parser = None
       self.stop_flag = False
       
   def run(self):
       try:
           # 執行登入
           self.progress.emit("初始化登入...")
           self.login_manager = EwantLogin(headless=False)
           
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
               search_text=self.search_text
           )
           
           try:
               self.parser.process_all_courses()
               self.finished.emit(True, "爬取完成")
               
           except Exception as e:
               self.finished.emit(False, f"爬取過程發生錯誤：{str(e)}")
               
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
        
        # 初始化設定檔
        self.config = Config()
        self.crawler_thread = None
        
        # 建立中央視窗
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 建立主要布局
        layout = QVBoxLayout(central_widget)
        
        # 建立登入區域
        login_group = QWidget()
        login_layout = QHBoxLayout(login_group)
        
        # 帳號輸入
        username_label = QLabel("帳號:")
        self.username_input = QLineEdit()
        login_layout.addWidget(username_label)
        login_layout.addWidget(self.username_input)
        
        # 密碼輸入
        password_label = QLabel("密碼:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        login_layout.addWidget(password_label)
        login_layout.addWidget(self.password_input)
        
        # 讀取設定檔並填入帳密
        saved_config = self.config.load_config()
        self.username_input.setText(saved_config.get('username', ''))
        self.password_input.setText(saved_config.get('password', ''))
        
        # 新增搜尋欄位
        search_group = QWidget()
        search_layout = QHBoxLayout(search_group)
        
        search_label = QLabel("搜尋課程:")
        self.search_input = QLineEdit()
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)

        # 加入主布局 登入區域
        layout.addWidget(login_group)
        # 加入主布局 搜尋欄位
        layout.addWidget(search_group)
        
        # 建立按鈕
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

        # 建立用於顯示課程名稱的列表
        # self.course_list = QListWidget()
        # layout.addWidget(self.course_list)

    def start_crawling(self):
        """開始爬取數據"""
        username = self.username_input.text()
        password = self.password_input.text()
        search_text = self.search_input.text()

        if not username or not password:
            QMessageBox.warning(self, "警告", "請輸入帳號和密碼")
            return

        self._update_ui_state(is_crawling=True)
        
        self.config.save_config(
            self.username_input.text(),
            self.password_input.text()
        )
        
        self.log_message("開始爬取程序...")
        self.crawler_thread = CrawlerThread(username, password, search_text)
        self.crawler_thread.progress.connect(self.log_message)
        self.crawler_thread.finished.connect(self.handle_crawler_result)
        self.crawler_thread.data_ready.connect(self.handle_crawler_data)
        self.crawler_thread.start()

    def stop_crawling(self):
        """停止爬取"""
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.log_message("正在停止爬蟲...")
            self.crawler_thread.stop()
            self.crawler_thread.wait()  # 等待執行緒結束
            self.crawler_thread = None
            self._update_ui_state(is_crawling=False)
    
    def export_report(self):
        """匯出報表"""
        self.log_message("開始匯出報表...")
        # TODO: 實作報表匯出功能
    
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
        # TODO: 實作資料處理邏輯
        """處理爬取到的資料"""
        for course in data:
            self.course_list.addItem(course['name'])
        pass

    def closeEvent(self, event):
        """視窗關閉事件"""
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.stop_crawling()
            self.crawler_thread.wait()
        event.accept()