import os
import sys
from typing import Optional
from pathlib import Path

class ResourceUtils:
    """資源檔案工具類別"""
    
    @staticmethod
    def get_app_path() -> str:
        """取得應用程式根目錄路徑"""
        if getattr(sys, 'frozen', False):
            # 如果是打包後的執行檔
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller 臨時資料夾
                return sys._MEIPASS
            return os.path.dirname(sys.executable)
        # 開發環境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    @staticmethod
    def get_resource_path(relative_path: str) -> Optional[str]:
        """
        取得資源檔案的完整路徑
        
        Args:
            relative_path: 相對於 resources 資料夾的路徑
            
        Returns:
            完整路徑,如果檔案不存在則返回 None
        """
        try:
            # 取得應用程式根目錄
            base_path = ResourceUtils.get_app_path()
            
            # 建構可能的路徑
            possible_paths = [
                # 開發環境路徑
                os.path.join(base_path, 'resources', relative_path),
                # PyInstaller 打包後路徑
                os.path.join(base_path, 'resources', relative_path),
                # 相對路徑
                os.path.join('resources', relative_path)
            ]
            
            # 尋找第一個存在的路徑
            for path in possible_paths:
                if os.path.exists(path):
                    return str(Path(path).resolve())
                    
            return None
            
        except Exception as e:
            print(f"取得資源路徑時發生錯誤: {str(e)}")
            return None