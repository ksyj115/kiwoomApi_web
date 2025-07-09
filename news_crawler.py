import requests
from bs4 import BeautifulSoup
import time

def search_naver_news_and_extract_content(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        search_url = f"https://search.naver.com/search.naver?where=news&query={query}"

        res = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        first_link_tag = soup.select_one("a.news_tit")
        if not first_link_tag:
            return ""

        news_url = first_link_tag["href"]

        # 해당 뉴스 페이지 접속
        article_res = requests.get(news_url, headers=headers)
        article_soup = BeautifulSoup(article_res.text, "html.parser")

        # 다양한 구조에 대응
        paragraphs = article_soup.select("article p") or article_soup.select("div#dic_area p")
        text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

        # 너무 길면 잘라내기
        return text[:1500] if text else ""
    except Exception as e:
        print(f"[뉴스 크롤링 오류] {e}")
        return ""
