from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import List, Dict
import time

class CourseParser:
    def __init__(self, driver, progress=None, search_text=None):
        self.driver = driver
        self.wait = WebDriverWait(driver, 180)
        self.progress = progress
        self.stop_crawling = False
        self.search_text = search_text

    def get_course_rows(self) -> List[Dict]:
        try:
            table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
            )
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            courses = []
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 8 and cells[0].text.strip() == "開課中":
                        courses.append({
                            'name': cells[2].text.strip(),
                            'row_idx': len(courses)
                        })
                except Exception as e:
                    print(f"處理行時發生錯誤: {str(e)}")
                    continue
            
            if self.progress:
                self.progress.emit(f"找到 {len(courses)} 門課程")
            return courses
            
        except TimeoutException:
            raise Exception("無法載入課程列表")

    def enter_course(self, course_idx: int) -> bool:
        try:
            table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
            )
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            if course_idx >= len(rows):
                print(f"找不到索引 {course_idx} 的課程")
                return False
                
            button = rows[course_idx].find_element(
                By.CSS_SELECTOR, 
                "input.btn.btn-primary[type='button'][value='進入課程']"
            )
            button.click()
            time.sleep(2)
            
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel-heading")))
            return True
            
        except Exception as e:
            print(f"進入課程時發生錯誤: {str(e)}")
            return False

    def back_to_course_list(self) -> bool:
        try:
            self.driver.execute_script("window.history.go(-1)")
            time.sleep(2)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table")))
            return True
        except Exception as e:
            print(f"返回課程列表時發生錯誤: {str(e)}")
            return False

    def process_all_courses(self) -> None:
        try:
            # 點擊搜尋按鈕
            search_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary.hidden-xs"))
            )
            search_button.click()
            time.sleep(2)
            
            # 檢查是否需要搜尋
            if self.search_text:
                search_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "fullname"))
                )
                search_input.clear()
                search_input.send_keys(self.search_text)
                
                # 點擊搜尋按鈕
                search_button.click()
                time.sleep(2)

            # 取得搜尋後的課程列表
            courses = self.get_course_rows()
            total_courses = len(courses)

            if self.progress:
                self.progress.emit(f"找到 {total_courses} 門課程")

            for idx in range(total_courses):
                if self.stop_crawling:
                    if self.progress:
                        self.progress.emit("使用者停止爬蟲")
                    break

                current_course = courses[idx]
                if self.progress:
                    self.progress.emit(f"處理第 {idx + 1}/{total_courses} 門課程: {current_course['name']}")

                if self.enter_course(current_course['row_idx']):
                    if self.progress:
                        self.progress.emit(f"成功進入課程：{current_course['name']}")
                    time.sleep(1)

                    if not self.back_to_course_list():
                        if self.progress:
                            self.progress.emit("無法返回課程列表，停止處理")
                        break
                    time.sleep(1)  # 在返回後多等待一秒
                else:
                    if self.progress:
                        self.progress.emit(f"無法進入課程：{current_course['name']}")

            # 全部處理完成後發出完成信號
            if self.progress:
                self.progress.emit("全部課程處理完成")
                self.progress_updated.emit(100)  # 進度條設為100%

        except Exception as e:
            error_msg = f"處理課程列表時發生錯誤：{str(e)}"
            print(error_msg)
            if self.progress:
                self.progress.emit(error_msg)