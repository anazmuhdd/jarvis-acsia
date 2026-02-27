import os
import gc
import httpx
import asyncio
import re
import json
import logging
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from selectolax.parser import HTMLParser
from urllib.parse import quote, urlparse

load_dotenv()

# Use logging instead of print to avoid buffering memory
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pulse AI - Intelligence Backend")

# --- Memory cleanup middleware ---
class MemoryCleanupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        gc.collect()
        return response

app.add_middleware(MemoryCleanupMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "qwen/qwen3-coder-480b-a35b-instruct")

# Lazy-init the client to avoid holding memory at startup
_nvidia_client = None

def get_nvidia_client():
    global _nvidia_client
    if _nvidia_client is None:
        _nvidia_client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=NVIDIA_API_KEY
        )
    return _nvidia_client

ASYNC_CLIENT_OPTIONS = {
    "verify": False,
    "timeout": 15.0,
    "follow_redirects": True,
    "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"},
    "limits": httpx.Limits(max_connections=5, max_keepalive_connections=2),
}

async def decode_google_news_url_async(url: str, client: httpx.AsyncClient) -> str:
    """Decode Google News URL using a shared client to avoid extra memory."""
    try:
        parsed = urlparse(url)
        path = parsed.path.split("/")
        if parsed.hostname != "news.google.com" or len(path) < 2:
            return url
        if path[-2] not in ("articles", "read"):
            return url
        base64_str = path[-1]
    except Exception:
        return url

    signature = None
    timestamp = None
    try:
        for url_fmt in [
            f"https://news.google.com/articles/{base64_str}",
            f"https://news.google.com/rss/articles/{base64_str}",
        ]:
            try:
                resp = await client.get(url_fmt)
                if resp.status_code == 200:
                    parser = HTMLParser(resp.text)
                    data_el = parser.css_first("c-wiz > div[jscontroller]")
                    if data_el:
                        signature = data_el.attributes.get("data-n-a-sg")
                        timestamp = data_el.attributes.get("data-n-a-ts")
                        if signature and timestamp:
                            del parser
                            break
                    del parser
            except Exception:
                continue

        if signature and timestamp:
            api_url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            payload = [
                "Fbv4je",
                f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{base64_str}",{timestamp},"{signature}"]',
            ]
            req_data = f"f.req={quote(json.dumps([[payload]]))}"

            api_resp = await client.post(
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

    except Exception:
        pass

    try:
        resp = await client.get(url)
        final_url = str(resp.url)
        if "news.google.com" not in final_url:
            return final_url
    except Exception:
        pass

    return url

async def get_article_image(google_url: str, client: httpx.AsyncClient) -> dict:
    final_url = google_url
    try:
        final_url = await decode_google_news_url_async(google_url, client)

        if "news.google.com" in final_url:
            return {"url": final_url, "image": None}

        response = await client.get(final_url, timeout=10.0)
        final_url = str(response.url)
        
        if response.status_code != 200:
            return {"url": final_url, "image": None}
        
        # Use selectolax (C-based, much lighter than BeautifulSoup) for image extraction
        tree = HTMLParser(response.text)
        del response  # Free response body immediately
        
        GOOGLE_DOMAINS = ["news.google.com", "gstatic.com", "googleusercontent.com"]
        result = {"url": final_url, "image": None}

        og_image = tree.css_first('meta[property="og:image"]')
        if og_image:
            img = og_image.attributes.get("content")
            if img and not any(d in img for d in GOOGLE_DOMAINS):
                result["image"] = img
                del tree
                return result
        
        twitter_image = tree.css_first('meta[name="twitter:image"]')
        if twitter_image:
            img = twitter_image.attributes.get("content")
            if img and not any(d in img for d in GOOGLE_DOMAINS):
                result["image"] = img
                del tree
                return result
            
        del tree
        return result
    except Exception:
        return {"url": final_url, "image": None}

@app.get("/api/news")
async def get_news(q: str = "technology", role: Optional[str] = None):
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
                content = response.content
                del response  # Free response immediately
                root = ET.fromstring(content)
                del content
                items = root.findall(".//item")
                
                parsed_items = []
                for item in items:
                    try:
                        pub_date = datetime.strptime(item.find("pubDate").text, "%a, %d %b %Y %H:%M:%S %Z")
                    except Exception:
                        pub_date = datetime.min
                    parsed_items.append((pub_date, item))
                
                parsed_items.sort(key=lambda x: x[0], reverse=True)
                top_items = [x[1] for x in parsed_items[:5]]
                del parsed_items, root  # Free XML tree
                
                # Process items sequentially to limit concurrent memory usage
                results = []
                for item in top_items:
                    results.append(await process_item(item))
                return results

            # Process queries sequentially to limit peak memory
            for query in queries:
                res = await fetch_query(query)
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
                except Exception:
                    return datetime.min

            unique_articles.sort(key=parse_date, reverse=True)
            result = {"articles": unique_articles}
        
        gc.collect()
        return result
            
    except Exception as e:
        gc.collect()
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/generate-topics")
async def generate_topics(profile: dict):
    try:
        role = profile.get("role", "Engineer")

        prompt = (
            f"Act as a professional intelligence analyst for a {role}. Your objective is to curate a highly "
            "informative, engaging, and learnable news feed that keeps this professional at the absolute "
            "forefront of their industry. Generate a generous list of 20 precise, high-quality Google News search queries.\n\n"
            "CRITICAL CONTEXT: Our company operates in the AUTOMOTIVE industry. You MUST include queries related to:\n"
            "- Emerging trends in Automotive and AI-driven automotive technologies.\n"
            f"- How a {role} operates, innovates, or builds organizations within the Automotive industry.\n"
            "- Building and maintaining software/systems/organizations for automotive.\n\n"
            "The queries MUST include specific patterns such as:\n"
            f"1. '{role} news latest' (Current industry events)\n"
            f"2. '{role} tools and frameworks 2025' (New technology adoption)\n"
            f"3. 'Technical deep dive into {role} principles in Automotive'\n"
            f"4. 'Latest {role} professional trends 2024-2025'\n"
            f"5. 'Innovative {role} case studies and breakthroughs in Automotive AI'\n\n"
            "Goal: Create a feed that is a 'learning experience' and keeps them updated on tools, news, and shifts.\n\n"
            "Rules:\n"
            "- No job search, recruitment, or career-advice related queries.\n"
            "- Return as a simple comma-separated list of strings.\n"
            "- Provide NO conversational filler, NO numbering, and NO markdown formatting.\n"
            "- Total count: Exactly 20 queries."
        )

        nvidia_client = get_nvidia_client()
        response = await nvidia_client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
        )

        raw_content = (response.choices[0].message.content or "").strip()
        del response  # Free response immediately
        raw_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
        
        queries = []
        for item in re.split(r'[,\n]', raw_content):
            clean_q = item.strip().strip('"').strip("'").strip()
            if clean_q and len(clean_q) > 3:
                queries.append(clean_q) 
        gc.collect()
        return {"queries": queries}
    except Exception as e:
        gc.collect()
        return {"queries": [f"{role} technology trends", "AI development", "engineering best practices"], "error": str(e)}

@app.get("/")
async def root():
    return {"message": "Welcome to the Jarvis ACSIA API"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
