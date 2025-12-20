import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from utils import GEN  # hoặc từ package genlogin
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
CHROMEDRIVER_PATH = os.path.join("../bin", "chromedriver.exe")

class ProfileController:
    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        self.driver = None
        self.ws_url = None
        self.gen_login = GEN()

    def start_profile(self):
        """Khởi chạy profile GenLogin và lấy wsEndpoint"""
        result = self.gen_login.start_profile(self.profile_id)
        print("Profile data:", result)

        if result.get("success") and "data" in result and "wsEndpoint" in result["data"]:
            self.ws_url = result["data"]["wsEndpoint"]
            print(f"[Profile {self.profile_id}] wsEndpoint: {self.ws_url}")
        else:
            raise RuntimeError(f"❌ Không thể mở profile {self.profile_id}")

    def connect_selenium(self):
        """Kết nối Selenium tới Chrome profile đang chạy"""
        if not self.ws_url:
            raise RuntimeError("❌ Chưa có wsEndpoint, phải start profile trước")

        step_start = time.perf_counter()
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Lấy debugger address từ wsEndpoint
        # ws://127.0.0.1:54016/devbins/browser/... -> 127.0.0.1:54016
        debugger_address = self.ws_url.replace("ws://", "").split("/")[0]
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)

        # Kết nối Selenium tới Chrome đang chạy
        self.driver = webdriver.Chrome(
            service=Service(CHROMEDRIVER_PATH),
            options=chrome_options
        )

        step_time = time.perf_counter() - step_start
        print(f"[Profile {self.profile_id}] ⏱️ [{step_time:.2f}s] Đã kết nối browser")

    def open_tiktok(self):
        """Điều khiển profile mở TikTok Studio"""
        if not self.driver:
            raise RuntimeError("❌ Chưa kết nối Selenium driver")

        step_start = time.perf_counter()
        self.driver.get("https://www.tiktok.com/tiktokstudio/upload?from=webapp")
        print(f"[Profile {self.profile_id}] TikTok opened, Title: {self.driver.title}")
        step_time = time.perf_counter() - step_start
        print(f"[Profile {self.profile_id}] ⏱️ [{step_time:.2f}s] Page loaded")
        file_input = WebDriverWait(self.driver, 5,poll_frequency=0.1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]'))
            )
        if(file_input):
            print('co file_input')

    def stop_profile(self):
        """Dừng profile GenLogin"""
        self.gen_login.stop_profile(self.profile_id)
        if self.driver:
            self.driver.quit()
        print(f"[Profile {self.profile_id}] Stopped")


# ==========================
# Ví dụ chạy
# ==========================
# if __name__ == "__main__":
#     profile_id = "25141883"
#     controller = ProfileController(profile_id)

#     controller.start_profile()     # Bật GenLogin profile
#     controller.connect_selenium()  # Kết nối Selenium
#     controller.open_tiktok()       # Mở TikTok Studio
#     time.sleep(5)                  # Thao tác thêm nếu muốn
#     controller.stop_profile()      # Dừng profile
