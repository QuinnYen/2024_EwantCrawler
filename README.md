# 課程資料爬蟲工具 Ver4.0

這是一個用於爬取Ewant課程平台上的課程資料的工具。  
![image](https://github.com/user-attachments/assets/6a971597-dd06-4572-905d-1e1bcebf48d6)



## 功能
- 使用Selenium自動登入Ewant平台
- 自動搜尋並瀏覽課程列表
- 獲取每門課程的選修人數與通過人數
- 將課程資料匯出Excel

## 如何使用
1. 確保已安裝Python 3.x和必要的依賴庫。
2. 執行`main.py`文件啟動程式。
3. 輸入Ewant平台的帳號和密碼，並可選擇搜尋關鍵字。
4. 點擊"開始爬取"按鈕開始爬取課程資料。
5. 爬取過程中可查看日誌訊息和課程列表。
6. 爬取完成後，可點擊"匯出報表"按鈕匯出課程資料。

## 配置文件
程式會自動讀取和儲存帳號密碼配置於系統的金鑰管理工具中，無需手動編輯設定檔。

## 注意事項
- 本程式僅供教育研究用途，請勿用於任何非法用途。
- 請遵守Ewant平台的使用條款和服務政策。
- 如果遇到任何問題，歡迎提出Issue或Pull Request。
