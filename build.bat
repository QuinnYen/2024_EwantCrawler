@echo off
REM 切換到批次檔所在的目錄
cd /d %~dp0

REM 啟動虛擬環境
call venv\Scripts\activate.bat

REM 執行打包程式
python build.py

REM 如果發生錯誤則暫停
if errorlevel 1 (
    echo 打包過程發生錯誤
    pause
    exit /b 1
)

echo 打包完成！
pause
exit /b 0