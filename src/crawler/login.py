from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from typing import Tuple


class EwantLogin:
    def __init__(self, headless: bool = False):
        """
        初始化登入類別
        Args:
            headless: 是否使用無頭模式（不顯示瀏覽器視窗）
        """
        self.driver = None
        self.headless = headless
        self.login_url = "https://report.ewant.org/Login"
    
    def init_driver(self) -> None:
        """初始化瀏覽器驅動"""
        options = webdriver.ChromeOptions()

        # 關閉Chrome密碼儲存提示
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)

        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-notifications')  # 禁用通知
        options.add_argument('--disable-popup-blocking')  # 禁用彈窗阻擋
        options.add_argument('--disable-infobars')  # 禁用信息列        
        options.add_argument('--disable-extensions')  # 禁用擴展
        options.add_argument("--disable-gpu") # 禁用GPU加速
        options.add_argument('--window-size=1920,1080')  # 設定視窗大小
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])  # 禁用自動控制提示

        # 设置user-agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36")

        # 使用 WebDriver Manager 自動管理 ChromeDriver
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.driver.implicitly_wait(180)

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        執行登入程序
        Args:
            username: 使用者名稱
            password: 密碼
        Returns:
            Tuple[bool, str]: (是否成功, 訊息)
        """
        try:
            if not self.driver:
                self.init_driver()
                
            # 訪問登入頁面
            self.driver.get(self.login_url)
            
            # 處理可能出現的警告視窗
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                alert.accept()  # 點擊確定按鈕
                # 重新載入頁面
                self.driver.get(self.login_url)
            except:
                pass  # 沒有警告視窗就繼續
                
            # 等待並點選同意條款
            agree_checkbox = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "agree"))
            )
            if not agree_checkbox.is_selected():
                agree_checkbox.click()
            
            # 填寫登入表單
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "user_email"))
            )
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "user_pw"))
            )
            
            username_input.clear()
            password_input.clear()
            
            username_input.send_keys(username)
            password_input.send_keys(password)
            
            # 提交表單
            submit_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], .btn-primary"))
            )
            submit_button.click()
            
            # 等待登入完成
            try:
                # 再次處理可能出現的警告視窗
                try:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    alert.accept()
                except:
                    pass
                    
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.current_url != self.login_url
                )
                
                # 等待搜尋按鈕出現並點擊
                search_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary.hidden-xs"))
                )
                search_button.click()
                
                # 等待課程列表載入
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
                )
                
                return True, "登入成功並顯示所有課程"
                
            except TimeoutException:
                # 檢查是否有錯誤訊息
                error_message = self.driver.find_element(By.CSS_SELECTOR, ".validation-summary-errors").text
                return False, f"登入失敗：{error_message}"
                
        except TimeoutException:
            return False, "等待元素超時"
        except WebDriverException as e:
            page_source = self.driver.page_source
            with open('error_page.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
            return False, f"瀏覽器錯誤：{str(e)}\n已保存頁面內容到 error_page.html"
        except Exception as e:
            return False, f"未知錯誤：{str(e)}"
    
    def get_driver(self):
        """獲取瀏覽器驅動實例"""
        return self.driver
    
    def close(self) -> None:
        """關閉瀏覽器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
