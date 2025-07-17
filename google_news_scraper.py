from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import time

def get_google_news_snippets(query="미국 증시", count=10):
    chromedriver_path = "C:/tools/chromedriver-win32/chromedriver.exe"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/117.0.0.0 Safari/537.36")

    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    try:
        url = f"https://www.google.com/search?q={query}&tbm=nws&hl=ko&gl=KR&ceid=KR:ko"
        driver.get(url)
        time.sleep(3)

        elements = driver.find_elements(By.CSS_SELECTOR, 'div.SoaBEf')
        results = []

        for el in elements[:count]:
            try:
                link_tag = el.find_element(By.CSS_SELECTOR, 'a.WlydOe')
                title = link_tag.text
                link = link_tag.get_attribute("href")

                snippet = el.find_element(By.CSS_SELECTOR, 'div.GI74Re').text

                results.append({
                    "title": title,
                    "summary": snippet,
                    "url": link
                })
            except Exception as e:
                print(f"[뉴스 파싱 오류] {e}")
                continue

        return results

    except Exception as e:
        print(f"[Google 뉴스 크롤링 실패] {e}")
        return []

    finally:
        driver.quit()
