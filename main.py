import os
import httpx
import uvicorn
import asyncio
import re
import base64
import json
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from selectolax.parser import HTMLParser
from urllib.parse import quote, urlparse

load_dotenv()

app = FastAPI(title="Pulse AI - Intelligence Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "qwen/qwen3-coder-480b-a35b-instruct")

client_nvidia = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

ASYNC_CLIENT_OPTIONS = {
    "verify": False,
    "timeout": 15.0,
    "follow_redirects": True,
    "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"}
}

async def decode_google_news_url_async(url: str) -> str:
    try:
        parsed = urlparse(url)
        path = parsed.path.split("/")
        if parsed.hostname != "news.google.com" or len(path) < 2:
            return url
        if path[-2] not in ("articles", "read"):
            return url
        base64_str = path[-1]
    except Exception as e:
        print(f"[Decoder] URL parse error: {e}")
        return url

    signature = None
    timestamp = None
    try:
        async with httpx.AsyncClient(**ASYNC_CLIENT_OPTIONS) as tmp_client:
            for url_fmt in [
                f"https://news.google.com/articles/{base64_str}",
                f"https://news.google.com/rss/articles/{base64_str}",
            ]:
                try:
                    resp = await tmp_client.get(url_fmt)
                    if resp.status_code == 200:
                        parser = HTMLParser(resp.text)
                        data_el = parser.css_first("c-wiz > div[jscontroller]")
                        if data_el:
                            signature = data_el.attributes.get("data-n-a-sg")
                            timestamp = data_el.attributes.get("data-n-a-ts")
                            if signature and timestamp:
                                break
                except Exception:
                    continue

            if signature and timestamp:
                api_url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
                payload = [
                    "Fbv4je",
                    f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{base64_str}",{timestamp},"{signature}"]',
                ]
                req_data = f"f.req={quote(json.dumps([[payload]]))}"

                api_resp = await tmp_client.post(
                    api_url,
                    headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                    data=req_data,
                )

                if api_resp.status_code == 200:
                    try:
                        parsed_data = json.loads(api_resp.text.split("\n\n")[1])[:-2]
                        decoded_url = json.loads(parsed_data[0][2])[1]
                        if decoded_url and "news.google.com" not in decoded_url:
                            return decoded_url
                    except (json.JSONDecodeError, IndexError, TypeError):
                        pass

    except Exception as e:
        print(f"[Decoder] Error: {e}")

    try:
        async with httpx.AsyncClient(**ASYNC_CLIENT_OPTIONS) as tmp_client:
            resp = await tmp_client.get(url)
            final_url = str(resp.url)
            if "news.google.com" not in final_url:
                return final_url
    except Exception:
        pass

    return url

async def get_article_image(google_url: str, client: httpx.AsyncClient) -> dict:
    final_url = google_url
    try:
        final_url = await decode_google_news_url_async(google_url)

        if "news.google.com" in final_url:
            return {"url": final_url, "image": None}

        response = await client.get(final_url, timeout=10.0)
        final_url = str(response.url)
        
        if response.status_code != 200:
            return {"url": final_url, "image": None}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        GOOGLE_DOMAINS = ["news.google.com", "gstatic.com", "googleusercontent.com"]

        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            img = og_image["content"]
            if not any(d in img for d in GOOGLE_DOMAINS):
                return {"url": final_url, "image": img}
        
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            img = twitter_image["content"]
            if not any(d in img for d in GOOGLE_DOMAINS):
                return {"url": final_url, "image": img}
            
        return {"url": final_url, "image": None}
    except Exception as e:
        print(f"[Image] Error for {final_url}: {e}")
        return {"url": final_url, "image": None}

@app.get("/api/news")
async def get_news(q: str = "technology", role: Optional[str] = None):
    print(f"Generating news for {q}...")
    try:
        queries = [query.strip() for query in q.split(",") if query.strip()]
        all_articles = []
        
        async with httpx.AsyncClient(**ASYNC_CLIENT_OPTIONS) as client:
            async def process_item(item):
                full_title = item.find("title").text
                title_parts = full_title.split(" - ")
                source = title_parts.pop() if len(title_parts) > 1 else "Global News"
                title = " - ".join(title_parts) if title_parts else full_title
                link = item.find("link").text
                pub_date_str = item.find("pubDate").text
                
                enrichment = await get_article_image(link, client)
                final_link = enrichment["url"]
                real_image = enrichment["image"]
                
                if not real_image or "news.google.com" in real_image:
                    real_image = None

                description_html = item.find("description").text or ""
                clean_description = re.sub(r'<[^>]*>', '', description_html)
                return {
                    "title": title,
                    "description": clean_description[:150] + "...",
                    "url": final_link,
                    "urlToImage": real_image,
                    "source": {"name": source},
                    "publishedAt": pub_date_str
                }

            async def fetch_query(query):
                rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
                response = await client.get(rss_url)
                root = ET.fromstring(response.content)
                items = root.findall(".//item")
                
                parsed_items = []
                for item in items:
                    try:
                        pub_date = datetime.strptime(item.find("pubDate").text, "%a, %d %b %Y %H:%M:%S %Z")
                    except:
                        pub_date = datetime.min
                    parsed_items.append((pub_date, item))
                
                parsed_items.sort(key=lambda x: x[0], reverse=True)
                top_items = [x[1] for x in parsed_items[:5]]
                return await asyncio.gather(*(process_item(item) for item in top_items))

            results = await asyncio.gather(*(fetch_query(q) for q in queries))
            for res in results:
                all_articles.extend(res)
            
            seen_urls = set()
            unique_articles = []
            for art in all_articles:
                if art["url"] not in seen_urls:
                    unique_articles.append(art)
                    seen_urls.add(art["url"])
            
            def parse_date(art):
                try:
                    return datetime.strptime(art["publishedAt"], "%a, %d %b %Y %H:%M:%S %Z")
                except:
                    return datetime.min

            unique_articles.sort(key=parse_date, reverse=True)
            return {"articles": unique_articles}
            
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/generate-topics")
async def generate_topics(profile: dict):
    print(f"Generating topics for {profile['role']}...")
    try:
        role = profile.get("role", "Engineer")

        prompt = (
            f"Act as a professional intelligence analyst for a {role}. Your objective is to curate a highly "
            "informative, engaging, and learnable news feed that keeps this professional at the absolute "
            "forefront of their industry. Generate a generous list of 15 precise, high-quality Google News search queries.\n\n"
            "The queries MUST include specific patterns such as:\n"
            f"1. '{role} news latest' (Current industry events)\n"
            f"2. '{role} tools and frameworks 2025' (New technology adoption)\n"
            f"3. 'Technical deep dive into {role} core principles'\n"
            f"4. 'Latest {role} professional trends 2024-2025'\n"
            f"5. 'Innovative {role} case studies and breakthroughs'\n\n"
            "Goal: Create a feed that is a 'learning experience' and keeps them updated on tools, news, and shifts.\n\n"
            "Rules:\n"
            "- No job search, recruitment, or career-advice related queries.\n"
            "- Return as a simple comma-separated list of strings.\n"
            "- Provide NO conversational filler, NO numbering, and NO markdown formatting.\n"
            "- Total count: Exactly 15 queries."
        )

        response = await client_nvidia.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
        )

        raw_content = (response.choices[0].message.content or "").strip()
        print(f"Raw content: {raw_content}")
        raw_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
        
        queries = []
        for item in re.split(r'[,\n]', raw_content):
            clean_q = item.strip().strip('"').strip("'").strip()
            if clean_q and len(clean_q) > 3:
                queries.append(clean_q) 
        print(f"Queries: {queries}")
        return {"queries": queries}
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return {"queries": [f"{role} technology trends", "AI development", "engineering best practices"], "error": str(e)}
@app.get("/")
async def root():
    return {"message": "Welcome to the Jarvis ACSIA API"}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
