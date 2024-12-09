import PyInstaller.__main__
import os
import shutil
import sys
from pathlib import Path

def clean_build():
    """清理舊的建置檔案"""
    print("清理舊的建置檔案...")
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']
    
    try:
        for dir_name in dirs_to_clean:
            if os.path.exists(dir_name):
                shutil.rmtree(dir_name)
        
        for pattern in files_to_clean:
            for file in Path('.').glob(pattern):
                file.unlink()
    except Exception as e:
        print(f"清理檔案時發生錯誤: {str(e)}")
        return False
    return True

def get_dll_paths():
    """取得所有需要的 DLL 路徑"""
    dll_paths = []
    
    # 專案內的 DLL
    project_dll_path = os.path.join('dependencies', 'dlls')
    if os.path.exists(project_dll_path):
        for dll in os.listdir(project_dll_path):
            if dll.endswith('.dll'):
                full_path = os.path.join(project_dll_path, dll)
                dll_paths.append(f'--add-binary={full_path};.')

    # Anaconda DLL
    anaconda_dll_path = os.path.join(os.environ.get('CONDA_PREFIX', ''), 'Library', 'bin')
    if os.path.exists(anaconda_dll_path):
        for dll in os.listdir(anaconda_dll_path):
            if dll.endswith('.dll'):
                full_path = os.path.join(anaconda_dll_path, dll)
                dll_paths.append(f'--add-binary={full_path};.')
                
    return dll_paths

def build():
    """執行打包"""
    try:
        if not clean_build():
            return False
        
        print("開始打包程式...")
        
        # 檢查資源檔案是否存在
        resources_path = os.path.join(os.path.dirname(__file__), 'resources')
        icon_path = os.path.join(resources_path, 'icon.ico')
        
        if not os.path.exists(resources_path):
            print("錯誤: 找不到 resources 資料夾")
            return False
            
        if not os.path.exists(icon_path):
            print("錯誤: 找不到圖示檔案")
            return False
        
        # 基本參數
        params = [
            'main.py',                    # 主程式
            '--name=EwantCrawler',        # 執行檔名稱
            '--onefile',                  # 單一檔案模式
            '--windowed',                 # GUI模式
            '--noconfirm',                # 覆寫已存在的檔案
            # '--icon=resources/icon.ico',  # 應用程式圖示
            f'--icon={icon_path}',        # 應用程式圖示
            '--add-data=resources;resources',  # 資源檔案
            '--collect-all=selenium',     # Selenium 相關檔案
            '--collect-all=PyQt6',        # PyQt6 相關檔案
            '--hidden-import=PyQt6',
            '--hidden-import=selenium',
            '--hidden-import=xml.parsers.expat',
            '--hidden-import=pkg_resources.py2_warn',
            '--hidden-import=pkg_resources',
            '--add-binary=venv/Lib/site-packages/selenium;selenium',
            '--add-data=venv/Lib/site-packages/PyQt6;PyQt6',
        ]
        
        # 加入所有 DLL
        dll_paths = get_dll_paths()
        params.extend(dll_paths)
        
        # 執行打包
        PyInstaller.__main__.run(params)
        
        print("\n打包完成!")
        print("執行檔位於: dist/EwantCrawler.exe")
        return True
        
    except Exception as e:
        print(f"\n打包過程發生錯誤: {str(e)}")
        return False

if __name__ == '__main__':
    try:
        if build():
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"執行時發生未預期的錯誤: {str(e)}")
        sys.exit(1)