import PyInstaller.__main__
import os
import shutil

def clean_dist():
    """清理之前的打包檔案"""
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)

def copy_additional_files():
    """複製需要的額外檔案到 dist 目錄"""
    # 建立設定檔目錄
    os.makedirs("dist/EwantCrawler/config", exist_ok=True)
    
    # 複製 ChromeDriver
    if os.path.exists("drivers/chromedriver.exe"):
        shutil.copy("drivers/chromedriver.exe", "dist/EwantCrawler")
    
    # 複製其他必要檔案（如果有的話）
    # shutil.copy("config.json", "dist/EwantCrawler/config")

def build():
    """執行打包程序"""
    # 清理舊檔案
    clean_dist()
    
    # PyInstaller 設定
    PyInstaller.__main__.run([
        'main.py',                        # 主程式
        '--name=EwantCrawler',            # 應用程式名稱
        '--windowed',                     # 使用視窗模式（不顯示控制台）
        '--onedir',                       # 製作單一目錄
        '--icon=resources/icon.ico',      # 應用程式圖示（如果有的話）
        '--add-data=src;src',             # 加入 src 目錄
        '--hidden-import=PyQt6',          # 確保 PyQt6 被包含
        '--hidden-import=selenium',        # 確保 Selenium 被包含
        '--clean',                        # 清理暫存檔
        '--noconfirm',                    # 不詢問確認
    ])
    
    # 複製額外檔案
    copy_additional_files()
    
    print("打包完成！")

if __name__ == "__main__":
    build()