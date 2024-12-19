import os
import sys

# 設定環境變數
def setup_environment():
    if getattr(sys, 'frozen', False):
        # 打包執行檔
        base_path = os.path.dirname(sys.executable)
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
    else:
        # 開發環境
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 將路徑加入環境變數
    if base_path not in os.environ['PATH']:
        os.environ['PATH'] = base_path + os.pathsep + os.environ['PATH']

if __name__ == "__main__":
    setup_environment()
    
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from src.ui.main_window import MainWindow
    from src.utils.resource_utils import ResourceUtils
    
    app = QApplication(sys.argv)
    
    # 設定應用程式圖示
    icon_path = ResourceUtils.get_resource_path('icon.ico')
    if icon_path:
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)  # 為整個應用程式設定圖示
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())