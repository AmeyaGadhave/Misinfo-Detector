import requests
from bs4 import BeautifulSoup

class Scraper:
    @staticmethod
    def scrape(url: str) -> dict:
        try:
            resp = requests.get(url, timeout=8, headers={'User-Agent':'Mozilla/5.0'})
            soup = BeautifulSoup(resp.text, "html.parser")

            title = (soup.title.string if soup.title else url)
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            text = " ".join(paragraphs) or soup.get_text(" ", strip=True)

            return {"title": title, "text": text}
        except Exception:
            return {"title": url, "text": ""}
