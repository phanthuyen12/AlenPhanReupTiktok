import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Style

class TikTokUploader:
    def __init__(self, driver):
        self.driver = driver  # Selenium WebDriver (đã attach tới TikTok Studio)

    # ===============================
    #  Đợi upload hoàn tất
    # ===============================
    def _wait_for_upload_complete(self, timeout=120):
        start_time = time.perf_counter()
        check_interval = 0.3
        
        while time.perf_counter() - start_time < timeout:
            try:
                # Kiểm tra nút Post
                post_button = self.driver.find_elements(By.CSS_SELECTOR, 'button[data-e2e="post_video_button"]')
                if post_button and post_button[0].is_enabled():
                    elapsed = time.perf_counter() - start_time
                    print(Fore.GREEN + f"⏱️ [{elapsed:.2f}s] ✅ Upload hoàn tất — nút Post sẵn sàng" + Style.RESET_ALL)
                    return True

                # Kiểm tra progress 100%
                progress_done = self.driver.execute_script("""
                    var el = document.querySelector('[class*="progress"], [class*="Progress"], [class*="upload"]');
                    if (!el) return false;
                    var t = el.textContent || el.innerText || '';
                    return t.includes('100%') || t.includes('hoàn thành') || t.includes('complete');
                """)
                if progress_done:
                    elapsed = time.perf_counter() - start_time
                    print(Fore.GREEN + f"⏱️ [{elapsed:.2f}s] ✅ Tiến trình upload đạt 100%" + Style.RESET_ALL)
                    time.sleep(1)
                    return True

            except Exception:
                pass

            time.sleep(check_interval)

        print(Fore.YELLOW + f"⚠️ Timeout sau {timeout}s — chưa xác nhận upload hoàn tất." + Style.RESET_ALL)
        return False

    # ===============================
    #  Upload video chính
    # ===============================
    def upload(self, local_path, caption=""):
        total_start = time.perf_counter()

        if not self.driver:
            print(Fore.RED + "❌ WebDriver chưa được khởi tạo" + Style.RESET_ALL)
            return False

        if not os.path.exists(local_path):
            print(Fore.RED + f"❌ File video không tồn tại: {local_path}" + Style.RESET_ALL)
            return False

        try:
            # --- B1: Chọn file upload ---
            file_input = WebDriverWait(self.driver, 10, poll_frequency=0.2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
            )
            file_input.send_keys(os.path.abspath(local_path))
            print(Fore.CYAN + f"🎬 Đã chọn file: {os.path.basename(local_path)}" + Style.RESET_ALL)

            # --- B2: Đợi upload hoàn tất ---
            upload_done = self._wait_for_upload_complete(timeout=120)

            # --- B3: Ghi caption (nếu có) ---
            if caption.strip():
                try:
                    caption_box = WebDriverWait(self.driver, 10, poll_frequency=0.1).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div.public-DraftEditor-content'))
                    )
                    caption_box.click()
                    ActionChains(self.driver).send_keys(caption.strip()).perform()
                    print(Fore.CYAN + f"📝 Đã nhập caption: {caption[:50]}..." + Style.RESET_ALL)
                except Exception as e:
                    print(Fore.YELLOW + f"⚠️ Không thể nhập caption: {e}" + Style.RESET_ALL)

            # --- B4: Click nút Post ---
            post_button = None
            attempts = 0
            max_attempts = 60
            success = False

            while attempts < max_attempts:
                attempts += 1

                # Tìm nút Post nếu chưa có
                if post_button is None:
                    try:
                        post_button = WebDriverWait(self.driver, 2, poll_frequency=0.1).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-e2e="post_video_button"]'))
                        )
                    except Exception:
                        print(f"🔁 [{attempts}/{max_attempts}] Đang đợi nút Post sẵn sàng...")
                        time.sleep(0.01)
                        if "tiktokstudio/content" in self.driver.current_url:
                            success = True
                            break
                        continue

                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post_button)
                    try:
                        ActionChains(self.driver).move_to_element(post_button).perform()
                    except Exception:
                        post_button = None
                        continue

                    # Click bằng JS để tăng độ ổn định
                    try:
                        post_text = post_button.find_element(By.CSS_SELECTOR, 'div.Button__content')
                        self.driver.execute_script("arguments[0].click();", post_text)
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", post_button)

                    print(Fore.CYAN + f"🖱 [{attempts}] Đã click nút Post, chờ phản hồi..." + Style.RESET_ALL)
                except Exception as e:
                    print(Fore.YELLOW + f"⚠️ [{attempts}] Lỗi khi click Post: {e}" + Style.RESET_ALL)

                time.sleep(0.5)

                # Kiểm tra nếu redirect sang /content
                try:
                    if "tiktokstudio/content" in self.driver.current_url:
                        success = True
                        print(Fore.GREEN + "✅ Upload thành công — chuyển hướng sang trang content!" + Style.RESET_ALL)
                        break
                except Exception:
                    pass

            # --- B5: Reload nếu thành công ---
            if success:
                print(Fore.GREEN + "🎉 Upload hoàn tất, reload trang upload mới..." + Style.RESET_ALL)
                self.driver.get("https://www.tiktok.com/tiktokstudio/upload?from=webapp")
            else:
                print(Fore.RED + f"❌ Sau {max_attempts} lần thử vẫn chưa thấy redirect /content." + Style.RESET_ALL)

            total_time = time.perf_counter() - total_start
            print(Fore.MAGENTA + f"⏱ Tổng thời gian upload: {total_time:.2f}s" + Style.RESET_ALL)
            return success

        except Exception as e:
            print(Fore.RED + f"❌ Upload video lỗi: {e}" + Style.RESET_ALL)
            return False
