from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import List, Dict, Tuple
import time
from datetime import datetime
import re

class CourseParser:
    def __init__(self, driver, progress=None, search_text=None, status_filters=None, start_date=None, end_date=None):
        self.driver = driver
        self.wait = WebDriverWait(driver, 30)
        self.progress = progress
        self.stop_crawling = False
        self.search_text = search_text
        self.status_filters = status_filters if status_filters else ["開課中"]
        self.start_date = start_date
        self.end_date = end_date
        self.courses = []

    def _parse_date(self, date_str):
        """解析日期字串，轉換為 datetime 物件"""
        try:
            # 移除所有空白字元
            date_str = date_str.strip()
            
            # ewant日期格式通常為 "2024-03-01" 或 "2024/03/01"
            patterns = [
                r'(\d{4})-(\d{2})-(\d{2})',  # 匹配 2024-03-01
                r'(\d{4})/(\d{2})/(\d{2})',  # 匹配 2024/03/01
            ]
            
            for pattern in patterns:
                match = re.match(pattern, date_str)
                if match:
                    year, month, day = map(int, match.groups())
                    return datetime(year, month, day)
            return None
        except Exception as e:
            if self.progress:
                self.progress.emit(f"日期解析錯誤 ({date_str}): {str(e)}")
            return None

    def _is_date_in_range(self, date_str):
        """檢查日期是否在指定範圍內"""
        if not (self.start_date and self.end_date):
            return True
            
        course_date = self._parse_date(date_str)
        if not course_date:
            if self.progress:
                self.progress.emit(f"無法解析日期: {date_str}")
            return True  # 如果無法解析日期，預設允許通過
            
        in_range = self.start_date <= course_date <= self.end_date
        if not in_range and self.progress:
            self.progress.emit(f"日期 {date_str} 不在指定範圍內")
        return in_range

    def get_course_rows(self) -> List[Dict]:
        """抓取課程列表"""
        try:
            table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
            )
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            courses = []
            
            total_rows = len(rows)
            filtered_count = 0
            date_filtered_count = 0
            
            for idx, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 8:
                        status = cells[0].text.strip()
                        start_time = cells[4].text.strip()
                        
                        # 檢查日期範圍
                        if not self._is_date_in_range(start_time):
                            if status in self.status_filters:
                                date_filtered_count += 1
                            continue
                            
                        if status in self.status_filters:
                            filtered_count += 1
                            courses.append({
                                'name': cells[2].text.strip(),
                                'status': status,
                                'start_time': start_time,
                                'end_time': cells[5].text.strip(),
                                'row_idx': idx,
                                'enrolled_count': 0
                            })
                except Exception as e:
                    print(f"處理第 {idx} 行時發生錯誤: {str(e)}")
                    continue
            
            if self.progress:
                # 重新組織訊息顯示順序
                msgs = [f"搜尋到 {total_rows} 門課程"]
                
                # 日期範圍資訊
                if self.start_date and self.end_date:
                    date_range = (f"日期範圍 {self.start_date.strftime('%Y-%m-%d')} "
                                f"到 {self.end_date.strftime('%Y-%m-%d')}")
                    msgs.append(date_range)
                
                # 狀態過濾資訊
                status_str = "、".join(self.status_filters)
                status_msg = f"符合「{status_str}」狀態的有 {filtered_count + date_filtered_count} 門"
                msgs.append(status_msg)
                
                # 日期過濾後的結果
                if self.start_date and self.end_date:
                    date_filter_msg = (f"符合日期範圍的有 {filtered_count} 門\n"
                                     f"（{date_filtered_count} 門課程因日期範圍不符而被過濾）")
                    msgs.append(date_filter_msg)
                
                # 發送完整訊息
                self.progress.emit("\n".join(msgs))
                
            self.courses = courses
            return courses
                
        except TimeoutException:
            raise Exception("無法載入課程列表")
        
    def get_enrolled_count(self) -> Dict:
        """抓取課程相關統計資訊"""
        try:
            # 找到課程選修資訊表格
            # tables = self.driver.find_elements(By.CSS_SELECTOR, ".table-responsive table")
            # 直接等待特定表格出現
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive"))
            )
            
            # 初始化回傳的資料結構
            stats = {
                '選修人數': {'台灣': 0, '中國大陸': 0, '其他': 0},
                '通過人數': {'台灣': 0, '中國大陸': 0, '其他': 0},
                '影片瀏覽次數': {'台灣': 0, '中國大陸': 0, '其他': 0},
                '作業測驗作答次數': {'台灣': 0, '中國大陸': 0, '其他': 0},
                '講義參考資料瀏覽次數': {'台灣': 0, '中國大陸': 0, '其他': 0},
                '討論次數': 0
            }
            
            # 直接找到目標表格
            tables = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "section.panel .table-responsive table"
            )
            current_type = '選修人數'
            
            for table in tables:
                try:
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            # 解析列的資料
                            if len(cells) == 3:  # 包含類型的列
                                current_type = cells[0].text.strip()
                                region = cells[1].text.strip()
                                count = self._parse_number(cells[2].text.strip())
                            else:  # 一般資料列
                                region = cells[0].text.strip()
                                count = self._parse_number(cells[1].text.strip())
                            
                            # 只處理有效的地區資料
                            if region in ["台灣", "中國大陸", "其他"]:
                                if current_type in stats and isinstance(stats[current_type], dict):
                                    stats[current_type][region] = count
                except Exception as e:
                    print(f"處理表格時發生錯誤: {str(e)}")
                    continue
            
            # 平行處理討論次數
            try:
                discussion_stats = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    ".panel-heading span.badge"
                )
                if discussion_stats:
                    stats['討論次數'] = self._parse_number(discussion_stats[0].text.strip())
            except Exception as e:
                if self.progress:
                    self.progress.emit(f"處理討論次數時發生錯誤: {str(e)}")
            
            return stats
                
        except Exception as e:
            print(f"抓取統計資訊時發生錯誤: {str(e)}")
            return None

    def _parse_number(self, text: str) -> int:
        """解析數字文字"""
        try:
            # 移除所有非數字字元
            number = ''.join(filter(str.isdigit, text))
            return int(number) if number else 0
        except:
            return 0
    
    def enter_course(self, course_idx: int) -> Tuple[bool, Dict]:
        """進入課程並抓取資料"""
        try:
            table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
            )
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            if course_idx >= len(rows):
                return False, None
                
            try:
                row = rows[course_idx]
                button = row.find_element(
                    By.CSS_SELECTOR, 
                    "input.btn.btn-primary[type='button'][value='進入課程']"
                )
                button.click()
                time.sleep(2)
                
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel-heading")))
                
                try:
                    summary_link = self.wait.until(
                        EC.element_to_be_clickable((By.LINK_TEXT, "課程摘要"))
                    )
                    summary_link.click()
                    time.sleep(2)
                    
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel-heading")))
                    
                    stats = self.get_enrolled_count()
                    return True, stats
                    
                except Exception as e:
                    print(f"點擊課程摘要時發生錯誤: {str(e)}")
                    return False, None
                    
            except Exception as e:
                print(f"處理第 {course_idx} 行時發生錯誤: {str(e)}")
                return False, None
                
        except Exception as e:
            print(f"進入課程時發生錯誤: {str(e)}")
            return False, None

    def process_all_courses(self) -> List[Dict]:
        try:
            # 處理搜尋條件
            if self.search_text:
                self.progress.emit(f"搜尋關鍵字: {self.search_text}")
                search_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "fullname"))
                )
                search_input.clear()
                search_input.send_keys(self.search_text)
                
            # 點擊搜尋按鈕
            search_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary.hidden-xs"))
            )
            search_button.click()
            time.sleep(2)
            
            # 取得課程列表
            courses = self.get_course_rows()
            total_courses = len(courses)

            # 顯示開始處理的課程
            if total_courses > 0:
                self.progress.emit(f"\n將開始處理 {total_courses} 門符合條件的課程...")
                self.progress.emit("------------------------")

            if total_courses == 0:
                self.progress.emit("未找到符合條件的課程")
                return []

            # 開始處理每一門課程
            self.progress.emit("\n開始擷取課程資料...")

            for idx, course in enumerate(courses, 1):
                if self.stop_crawling:
                    self.progress.emit("使用者停止爬蟲")
                    break

                self.progress.emit(f"正在處理第 {idx}/{total_courses} 門課程")
                self.progress.emit(f"課程名稱: {course['name']}")
                self.progress.emit(f"課程狀態: {course['status']}")

                success, stats = self.enter_course(course['row_idx'])
                if success:
                    course['stats'] = stats
                    
                    # 計算該課程的選修總人數
                    if stats:
                        total_enrolled = sum(stats['選修人數'].values())
                        self.progress.emit(f"選修總人數: {total_enrolled} 人")
                    
                    if hasattr(self, 'data_ready'):
                        self.data_ready.emit(courses[:idx])
                    
                    time.sleep(1)

                    if not self.back_to_course_list():
                        self.progress.emit("無法返回課程列表，停止處理")
                        return courses
                    
                    time.sleep(1)
                    self.progress.emit("------------------------")  # 分隔線
                else:
                    self.progress.emit(f"無法擷取課程資料：{course['name']}")
                    return courses

            self.progress.emit(f"\n資料擷取完成! 共處理 {total_courses} 門課程")
            return courses

        except Exception as e:
            error_msg = f"處理課程列表時發生錯誤：{str(e)}"
            print(error_msg)
            if self.progress:
                self.progress.emit(error_msg)
            return []

    def back_to_course_list(self) -> bool:
        """返回課程列表頁面"""
        try:
            # 使用歷史返回保留搜尋狀態
            self.driver.execute_script("window.history.go(-2)")
            
            # 使用明確的等待替代固定延遲
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
            )
            
            # 確保表格已載入（可選，如果發現有時候會抓不到資料再加入）
            # self.wait.until(
            #     lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "tbody tr")) > 0
            # )
            
            return True
        except Exception as e:
            if self.progress:
                self.progress.emit(f"返回課程列表時發生錯誤: {str(e)}")
            return False
