import json
import os
from typing import Dict, Optional

class Config:
    def __init__(self):
        self.config_file = 'config.json'
        self.default_config = {
            'username': '',
            'password': ''
        }
    
    def load_config(self) -> Dict[str, str]:
        """讀取設定檔"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.default_config
        except Exception:
            return self.default_config
    
    def save_config(self, username: str, password: str) -> None:
        """儲存設定檔"""
        config = {
            'username': username,
            'password': password
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"儲存設定檔時發生錯誤：{str(e)}")