from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

driver.get("https://cargillsonline.com/Index")

wait = WebDriverWait(driver, 20)

# WAIT until AngularJS promotions load
wait.until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img"))
)

print("Page loaded with dynamic content ✔")

# Now extract banners/promotions
images = driver.find_elements(By.TAG_NAME, "img")

for img in images:
    src = img.get_attribute("src")
    alt = img.get_attribute("alt")
    if src:
        print(src, alt)

driver.quit()