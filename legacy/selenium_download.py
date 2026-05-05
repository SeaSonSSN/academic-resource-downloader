#!/usr/bin/env python3
"""Download analog IC books using Selenium + Chrome"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import os

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--proxy-server=http://127.0.0.1:7890')

service = Service(executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe')
driver = webdriver.Chrome(service=service, options=chrome_options)

out_dir = r'C:\Users\ben20\Desktop\模拟IC四大名著'
os.makedirs(out_dir, exist_ok=True)

books = [
    'Analysis and Design of Analog Integrated Circuits Gray',
    'CMOS Analog Circuit Design Allen Holberg',
    'Analog Design Essentials Sansen',
    'Analog Integrated Circuit Design Johns Martin',
    'The Art of Electronics Horowitz Hill',
    'The Art of Analog Layout Hastings',
]

for book in books:
    print(f'\n=== Searching: {book} ===')
    try:
        # Search on libgen.is
        search_url = f'https://libgen.is/search?q={book.replace(" ", "+")}'
        driver.get(search_url)
        time.sleep(3)

        # Find result links
        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/book/"]')
        print(f'Found {len(links)} book links')

        if links:
            first_link = links[0].get_attribute('href')
            print(f'Opening: {first_link}')
            driver.get(first_link)
            time.sleep(2)

            # Try to find download link
            download_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*=".pdf"], a[href*="download"]')
            for dl in download_links[:5]:
                href = dl.get_attribute('href')
                print(f'  Download link: {href}')

    except Exception as e:
        print(f'Error: {e}')

driver.quit()
print('\nDone')