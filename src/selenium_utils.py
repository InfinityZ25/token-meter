import importlib
import os
import tempfile
from contextlib import contextmanager
from io import BytesIO

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


@contextmanager
def get_driver(headless=True, width=1920, height=1080):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--window-size={width},{height}')

    driver = webdriver.Chrome(service=Service(
        ChromeDriverManager().install()), options=options)
    try:
        yield driver
    finally:
        driver.quit()


class SeleniumUtils:
    @staticmethod
    def take_screenshot(driver, filename):
        screenshot = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(screenshot))
        img.save(filename)
        return f"Screenshot saved as {filename}"

    @staticmethod
    def wait_for_element(driver, by, value, timeout=10):
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    @staticmethod
    def scroll_to_bottom(driver):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")


def execute_temp_script(code: str, script_name: str = "temp_script", headless=True) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = os.path.join(temp_dir, f"{script_name}.py")

        # Modify the code to import utility functions
        modified_code = f"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

class SeleniumUtils:
    {SeleniumUtils.take_screenshot.__code__.co_code}
    {SeleniumUtils.wait_for_element.__code__.co_code}
    {SeleniumUtils.scroll_to_bottom.__code__.co_code}

{code}
"""

        with open(script_path, 'w') as f:
            f.write(modified_code)

        try:
            spec = importlib.util.spec_from_file_location(
                script_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with get_driver(headless=headless) as driver:
                if hasattr(module, 'custom_selenium_interaction'):
                    result = module.custom_selenium_interaction(driver)
                    return str(result)
                else:
                    return "Error: custom_selenium_interaction function not found in the code."
        except Exception as e:
            return f"An error occurred while executing the custom code: {str(e)}"


def selenium_web_interaction(url: str, take_screenshot: bool = False, headless=True) -> str:
    with get_driver(headless=headless) as driver:
        if take_screenshot:
            return SeleniumUtils.take_screenshot(driver, url)

        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))

            title = driver.title
            content = driver.find_element(By.TAG_NAME, "body").text
            return f"Title: {title}\n\nContent preview:\n{content[:500]}..."
        except Exception as e:
            return f"An error occurred while fetching the webpage: {str(e)}"
