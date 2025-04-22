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
        self.progress_percent = None
        self.time_remaining = None
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
            
        # 只返回是否在範圍內的結果，不顯示每個被過濾的日期
        return self.start_date <= course_date <= self.end_date

    def get_course_rows(self) -> List[Dict]:
        """抓取課程列表"""
        try:
            table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table-responsive table"))
            )
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            courses = []
            
            total_rows = len(rows)  # 這裡定義了 total_rows 變數
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
                    date_range = (f"日期範圍篩選: {self.start_date.strftime('%Y-%m-%d')} "
                                f"至 {self.end_date.strftime('%Y-%m-%d')}")
                    msgs.append(date_range)
                
                # 狀態過濾資訊
                status_str = "、".join(self.status_filters)
                status_msg = f"符合「{status_str}」狀態的有 {filtered_count + date_filtered_count} 門"
                msgs.append(status_msg)
                
                # 日期過濾後的結果 - 改為更簡潔的訊息
                if self.start_date and self.end_date and date_filtered_count > 0:
                    date_filter_msg = f"符合狀態和日期範圍的有 {filtered_count} 門課程"
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
            # 等待特定表格出現
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
                '講義參考資料瀏覽人數': {'台灣': 0, '中國大陸': 0, '其他': 0},
                '討論次數': 0,
                '使用行動載具瀏覽影片次數': 'N/A'  # 預設值為 N/A
            }
            
            # 找到所有表格
            tables = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "section.panel .table-responsive table"
            )
            
            # 處理兩個表格的資料
            for table_idx, table in enumerate(tables):
                try:
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    current_type = ''
                    
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        # 跳過空行或格式不符的行
                        if len(cells) < 2:
                            continue
                        
                        # 處理不同格式的表格行
                        if len(cells) == 3:  # 包含類型的列
                            type_text = cells[0].text.strip()
                            region = cells[1].text.strip()
                            count = self._parse_number(cells[2].text.strip())
                            
                            # 如果有rowspan，那麼這是一個新類型
                            if 'rowspan' in cells[0].get_attribute('outerHTML').lower():
                                current_type = type_text
                            
                            # 改進的類型匹配邏輯
                            if '講義' in current_type and '參考資料' in current_type:
                                if '瀏覽人數' in current_type:
                                    # 講義/參考資料瀏覽人數
                                    if region in ["台灣", "中國大陸", "其他"]:
                                        stats['講義參考資料瀏覽人數'][region] = count
                                elif '瀏覽次數' in current_type:
                                    # 講義/參考資料瀏覽次數
                                    if region in ["台灣", "中國大陸", "其他"]:
                                        stats['講義參考資料瀏覽次數'][region] = count
                            else:
                                # 其他正常資料的處理
                                if region in ["台灣", "中國大陸", "其他"] and current_type in stats and isinstance(stats[current_type], dict):
                                    stats[current_type][region] = count
                                    
                        elif len(cells) == 2:  # 一般資料列或討論次數
                            col1_text = cells[0].text.strip()
                            col2_text = cells[1].text.strip()
                            
                            # 處理討論次數
                            if '討論次數' in col1_text:
                                stats['討論次數'] = self._parse_number(col2_text)
                            # 處理行動載具瀏覽影片次數
                            elif '使用行動載具瀏覽影片次數' in col1_text:
                                # 如果是純數字就解析，否則保留原值(可能是N/A)
                                try:
                                    stats['使用行動載具瀏覽影片次數'] = self._parse_number(col2_text)
                                except:
                                    stats['使用行動載具瀏覽影片次數'] = col2_text.strip()
                            # 處理普通地區資料
                            elif col1_text in ["台灣", "中國大陸", "其他"] and current_type in stats and isinstance(stats[current_type], dict):
                                stats[current_type][col1_text] = self._parse_number(col2_text)
                
                except Exception as e:
                    if self.progress:
                        self.progress.emit(f"處理第 {table_idx+1} 個表格時發生錯誤: {str(e)}")
                    print(f"處理表格時發生錯誤: {str(e)}")
                    continue
            
            # 額外處理：直接從表格查找特定文字
            try:
                # 尋找講義/參考資料瀏覽人數和次數的行
                all_cells = self.driver.find_elements(By.CSS_SELECTOR, ".table tr td")
                for cell_idx, cell in enumerate(all_cells):
                    cell_text = cell.text.strip()
                    
                    # 檢查是否為講義/參考資料瀏覽人數
                    if '講義' in cell_text and '參考資料' in cell_text and '瀏覽人數' in cell_text:
                        try:
                            # 嘗試獲取相應的地區及數值
                            region_cells = all_cells[cell_idx+1:cell_idx+7]  # 抓取後續6個單元格
                            
                            # 遍歷每個可能的地區單元格
                            for i in range(0, len(region_cells), 2):
                                if i+1 < len(region_cells):
                                    region = region_cells[i].text.strip()
                                    if region in ["台灣", "中國大陸", "其他"]:
                                        count = self._parse_number(region_cells[i+1].text.strip())
                                        stats['講義參考資料瀏覽人數'][region] = count
                        except Exception as e:
                            print(f"處理講義/參考資料瀏覽人數時發生錯誤: {str(e)}")
                    
                    # 檢查是否為講義/參考資料瀏覽次數
                    if '講義' in cell_text and '參考資料' in cell_text and '瀏覽次數' in cell_text:
                        try:
                            # 嘗試獲取相應的地區及數值
                            region_cells = all_cells[cell_idx+1:cell_idx+7]  # 抓取後續6個單元格
                            
                            # 遍歷每個可能的地區單元格
                            for i in range(0, len(region_cells), 2):
                                if i+1 < len(region_cells):
                                    region = region_cells[i].text.strip()
                                    if region in ["台灣", "中國大陸", "其他"]:
                                        count = self._parse_number(region_cells[i+1].text.strip())
                                        stats['講義參考資料瀏覽次數'][region] = count
                        except Exception as e:
                            print(f"處理講義/參考資料瀏覽次數時發生錯誤: {str(e)}")
                    
                    # 檢查是否為使用行動載具瀏覽影片次數
                    if '使用行動載具瀏覽影片次數' in cell_text:
                        try:
                            # 檢查是否有下一個單元格
                            if cell_idx + 1 < len(all_cells):
                                value_text = all_cells[cell_idx+1].text.strip()
                                try:
                                    stats['使用行動載具瀏覽影片次數'] = self._parse_number(value_text)
                                except:
                                    stats['使用行動載具瀏覽影片次數'] = value_text
                        except Exception as e:
                            print(f"處理使用行動載具瀏覽影片次數時發生錯誤: {str(e)}")
                    
                    # 檢查是否為討論次數
                    if '討論次數' in cell_text and not '人數' in cell_text:
                        try:
                            # 討論次數通常在下一個單元格
                            if cell_idx + 1 < len(all_cells):
                                count = self._parse_number(all_cells[cell_idx+1].text.strip())
                                stats['討論次數'] = count
                        except Exception as e:
                            print(f"處理討論次數時發生錯誤: {str(e)}")
            except Exception as e:
                if self.progress:
                    self.progress.emit(f"直接查找特定文字時發生錯誤: {str(e)}")
            
            return stats
                
        except Exception as e:
            if self.progress:
                self.progress.emit(f"抓取統計資訊時發生錯誤: {str(e)}")
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
            start_process_time = time.time()  # 使用已導入的 time 模組
            
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
            
            # 添加時間追蹤
            start_time = time.time()
            processed_times = []
            
            for idx, course in enumerate(courses, 1):
                course_start_time = time.time()
                
                if self.stop_crawling:
                    self.progress.emit("使用者停止爬蟲")
                    break
                    
                # 計算進度百分比
                progress_percent = int((idx - 1) / total_courses * 100)
                
                # 發送進度百分比
                if hasattr(self, 'progress_percent'):
                    self.progress_percent.emit(progress_percent)
                
                # 計算預估剩餘時間
                elapsed_time = time.time() - start_time
                if idx > 1:
                    avg_time_per_course = elapsed_time / (idx - 1)
                    remaining_courses = total_courses - (idx - 1)
                    estimated_time_left = avg_time_per_course * remaining_courses
                    
                    # 格式化時間
                    hours, remainder = divmod(estimated_time_left, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = ""
                    if hours > 0:
                        time_str += f"{int(hours)}小時"
                    if minutes > 0:
                        time_str += f"{int(minutes)}分鐘"
                    time_str += f"{int(seconds)}秒"
                    
                    # 發送剩餘時間
                    if hasattr(self, 'time_remaining'):
                        self.time_remaining.emit(time_str)
                
                # 修改日誌訊息，不再包含進度百分比和剩餘時間
                self.progress.emit(f"正在處理：{course['name']}")
                self.progress.emit(f"課程狀態：{course['status']}")
                self.progress.emit(f"開課時間：{course['start_time']}")

                success, stats = self.enter_course(course['row_idx'])
                if success:
                    course['stats'] = stats
                    
                    # 計算該課程的選修總人數
                    if stats:
                        total_enrolled = sum(stats['選修人數'].values())
                        self.progress.emit(f"選修總人數：{total_enrolled} 人")
                    
                    if hasattr(self, 'data_ready'):
                        self.data_ready.emit(courses[:idx])
                    
                    time.sleep(1)

                    if not self.back_to_course_list():
                        self.progress.emit("無法返回課程列表，停止處理")
                        return courses
                    
                    time.sleep(1)
                    self.progress.emit("------------------------")  # 分隔線
                    
                    # 更新進度為當前課程完成的百分比
                    progress_percent = int(idx / total_courses * 100)
                    if hasattr(self, 'progress_percent'):
                        self.progress_percent.emit(progress_percent)
                    
                    # 記錄課程處理時間
                    course_elapsed = time.time() - course_start_time
                    processed_times.append(course_elapsed)
                    
                else:
                    self.progress.emit(f"無法擷取課程資料：{course['name']}")
                    return courses

            # 最終更新進度為100%
            if hasattr(self, 'progress_percent'):
                self.progress_percent.emit(100)
            
            # 清除剩餘時間
            if hasattr(self, 'time_remaining'):
                self.time_remaining.emit("完成")
                
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
