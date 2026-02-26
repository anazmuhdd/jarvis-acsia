import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000"

ROLES = [
    "AI Engineer",
    "Software Developer",
    "CEO",
    "Project Manager",
    "Data Scientist"
]

async def test_role_flow(client, role):
    print(f"\n" + "="*50)
    print(f"🚀 TESTING ROLE: {role}")
    print("="*50)

    # 1. Generate Topics
    print(f"📡 Requesting topics for {role}...")
    try:
        gen_resp = await client.post(
            f"{BASE_URL}/api/generate-topics",
            json={"role": role},
            timeout=130.0
        )
        if gen_resp.status_code != 200:
            print(f"❌ Topic generation failed ({gen_resp.status_code}): {gen_resp.text}")
            return

        data = gen_resp.json()
        queries = data.get("queries", [])
        print(f"✅ Success! Generated {len(queries)} queries:")
        for i, q in enumerate(queries, 1):
            print(f"   {i}. {q}")
        
    except Exception as e:
        print(f"💥 Error calling generate-topics: {e}")
        return

    # 2. Fetch News (we'll fetch for the first 3 topics to keep it fast)
    test_queries = ",".join(queries[:3])
    print(f"\n📰 Fetching news for topics: {test_queries}...")
    
    try:
        news_resp = await client.get(
            f"{BASE_URL}/api/news",
            params={"q": test_queries},
            timeout=60.0
        )
        if news_resp.status_code != 200:
            print(f"❌ News fetch failed ({news_resp.status_code}): {news_resp.text}")
            return

        news_data = news_resp.json()
        articles = news_data.get("articles", [])
        print(f"✅ Success! Fetched {len(articles)} unique articles.")

        # 3. Verify decoding & display snippets
        print("\n🔍 Verifying URL decoding (Top 3 articles):")
        for i, article in enumerate(articles[:3]):
            url = article.get('url', '')
            decoded = "news.google.com" not in url
            status = "✅ DECODED" if decoded else "❌ FAILED (STILL GOOGLE LINK)"
            print(f"   [{i+1}] {status}")
            print(f"       Title: {article.get('title')[:80]}...")
            print(f"       Source: {article.get('source', {}).get('name')}")
            print(f"       URL: {url[:80]}...")

    except Exception as e:
        print(f"💥 Error calling news API: {e}")

async def main():
    print("🛠️ Pulse AI Manual Integration Test")
    print(f"📍 Target: {BASE_URL}")
    print("⚠️ Ensure the server is running (python main.py) before proceeding.\n")

    async with httpx.AsyncClient() as client:
        # Check if server is up
        try:
            await client.get(f"{BASE_URL}/docs")
        except Exception:
            print(f"❌ ERROR: Could not connect to {BASE_URL}. Is the server running?")
            return

        for role in ROLES:
            await test_role_flow(client, role)

    print("\n" + "="*50)
    print("🎉 ALL TESTS COMPLETED")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
