import keyring
import os
from typing import Dict

class Config:
    def __init__(self):
        self.app_name = "EwantCrawler"  # 應用程式名稱
        self.default_config = {
            'username': '',
            'password': ''
        }
    
    def load_config(self) -> Dict[str, str]:
        """讀取設定"""
        try:
            # 先取得使用者名稱（不加密儲存）
            username = keyring.get_password(self.app_name, "username") or ""
            # 再用使用者名稱取得對應的密碼
            password = keyring.get_password(self.app_name, username) if username else ""
            
            return {
                'username': username,
                'password': password
            }
        except Exception:
            return self.default_config
    
    def save_config(self, username: str, password: str) -> None:
        """儲存設定"""
        try:
            # 儲存使用者名稱
            keyring.set_password(self.app_name, "username", username)
            # 儲存密碼
            if username:
                keyring.set_password(self.app_name, username, password)
                
        except Exception as e:
            print(f"儲存設定時發生錯誤：{str(e)}")