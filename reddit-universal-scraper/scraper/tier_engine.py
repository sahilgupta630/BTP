"""
3-Tier Fallback Reddit Scraper Engine
Tier 1: OAuth (asyncpraw)
Tier 2: Proxies (FreeProxy + aiohttp)
Tier 3: Tor Network (stem + aiohttp_socks)
"""
import asyncio
import aiohttp
import os
import sys
from aiohttp_socks import ProxyConnector
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, USER_AGENT, TOR_PORT, TOR_CONTROL_PORT, TOR_PASSWORD

# Ensure asyncpraw is imported if keys exist
try:
    import asyncpraw
except ImportError:
    asyncpraw = None

try:
    from fp.fp import FreeProxy
except ImportError:
    FreeProxy = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

try:
    from stem import Signal
    from stem.control import Controller
except ImportError:
    Signal = None
    Controller = None

class TieredScraper:
    def __init__(self, target, limit=100, is_user=False, is_search=False):
        self.target = target
        self.limit = limit
        self.is_user = is_user
        self.is_search = is_search
        self.total_fetched = 0
        self.current_tier = 1
        self.results = []
        self.after = None
        
    def _rotate_tor_ip(self):
        """Sends NEWNYM signal to Tor to get a new IP address."""
        if not Controller:
            print("❌ Stem library not installed, cannot rotate Tor IP.")
            return False
            
        print("🧅 [Tier 3] Requesting new Tor IP address...")
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
                if TOR_PASSWORD:
                    controller.authenticate(password=TOR_PASSWORD)
                else:
                    controller.authenticate()
                controller.signal(Signal.NEWNYM)
            print("🧅 [Tier 3] Tor IP successfully rotated!")
            return True
        except Exception as e:
            print(f"⚠️ Failed to rotate Tor IP: {e}")
            return False

    async def fetch_tier_1_praw(self):
        """Tier 1: Official Reddit API via AsyncPRAW"""
        if not asyncpraw or not REDDIT_CLIENT_ID:
            print("⚠️ [Tier 1] Missing PRAW credentials. Falling back to Tier 2.")
            self.current_tier = 2
            return False

        print("🥇 [Tier 1] Starting OAuth Scraping (Extremely Fast)...")
        try:
            reddit = asyncpraw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=USER_AGENT,
            )
            
            remaining = self.limit - self.total_fetched
            
            if self.is_search:
                # Global search across all of Reddit
                iterator = reddit.subreddit("all").search(self.target, limit=remaining)
            elif self.is_user:
                # User profile
                iterator = reddit.redditor(self.target).submissions.new(limit=remaining)
            else:
                # Specific Subreddit
                iterator = reddit.subreddit(self.target).new(limit=remaining)
            
            async for submission in iterator:
                self.results.append({
                    "id": submission.id,
                    "title": submission.title,
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "permalink": submission.permalink,
                    "url": submission.url,
                    "score": submission.score,
                    "created_utc": submission.created_utc,
                    "source": "Tier1_PRAW"
                })
                self.total_fetched += 1
                
            await reddit.close()
            return True
            
        except Exception as e:
            if "429" in str(e):
                print("❌ [Tier 1] Rate limit heavily exceeded or IP blocked! Falling back to Tier 2.")
            else:
                print(f"❌ [Tier 1] API Error: {e}. Falling back to Tier 2.")
            self.current_tier = 2
            try:
                await reddit.close()
            except:
                pass
            return False

    async def fetch_tier_2_proxy(self):
        """Tier 2: Public Proxy scraping via FreeProxy and aiohttp"""
        if not FreeProxy:
            print("⚠️ [Tier 2] FreeProxy library missing. Falling back to Tier 3.")
            self.current_tier = 3
            return False
            
        print("🥈 [Tier 2] Starting Proxy JSON Scraping...")
        
        try:
            # Scrape a random free proxy (Run in thread to prevent blocking the event loop)
            try:
                proxy_url = await asyncio.wait_for(
                    asyncio.to_thread(FreeProxy(rand=True, timeout=1).get),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                raise Exception("Proxy scraping timed out after 15 seconds")
                
            print(f"   📡 Using Free Proxy: {proxy_url}")
            
            remaining = min(100, self.limit - self.total_fetched)
            
            import urllib.parse
            if self.is_search:
                encoded_query = urllib.parse.quote(self.target)
                url = f"https://old.reddit.com/search.json?q={encoded_query}&limit={remaining}"
            elif self.is_user:
                url = f"https://old.reddit.com/user/{self.target}/submitted.json?limit={remaining}"
            else:
                url = f"https://old.reddit.com/r/{self.target}/new.json?limit={remaining}"
                
            if self.after:
                url += f"&after={self.after}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, proxy=proxy_url, timeout=10, headers={"User-Agent": USER_AGENT}) as response:
                    if response.status == 200:
                        data = await response.json()
                        for child in data['data']['children']:
                            p = child['data']
                            self.results.append({
                                "id": p.get('id'),
                                "title": p.get('title'),
                                "author": p.get('author'),
                                "permalink": p.get('permalink'),
                                "url": p.get('url'),
                                "score": p.get('score'),
                                "created_utc": p.get('created_utc'),
                                "source": "Tier2_Proxy"
                            })
                            self.total_fetched += 1
                        print("   ✅ Proxy extraction successful!")
                        self.after = data['data'].get('after')
                        return True
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            print(f"❌ [Tier 2] Proxy failed or blocked ({e}). Falling back to Tier 3.")
            self.current_tier = 3
            return False

    async def fetch_tier_3_tor(self):
        """Tier 3: Tor Network via Headless Chromium (Playwright)"""
        print("🥉 [Tier 3] Starting Tor Headless Browser Scraping (Bypassing Javascript walls)...")
        
        if not async_playwright:
            print("❌ [Tier 3] Playwright is not installed. Please run: pip install playwright && playwright install chromium")
            return False
            
        remaining = min(100, self.limit - self.total_fetched)
        
        import urllib.parse
        if self.is_search:
            encoded_query = urllib.parse.quote(self.target)
            url = f"https://old.reddit.com/search.json?q={encoded_query}&limit={remaining}"
        elif self.is_user:
            url = f"https://old.reddit.com/user/{self.target}/submitted.json?limit={remaining}"
        else:
            url = f"https://old.reddit.com/r/{self.target}/new.json?limit={remaining}"
            
        if self.after:
            url += f"&after={self.after}"
            
        print(f"   🌐 Headless browser navigating to: {url}")
        
        import json
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    proxy={"server": f"socks5://127.0.0.1:{TOR_PORT}"},
                    headless=False
                )
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                page = await context.new_page()
                
                # Navigate to the URL and wait for the redirect
                try:
                    await page.goto(url, timeout=30000)
                except Exception as nav_e:
                    print(f"⚠️ Navigation timeout or error: {nav_e}")
                
                # The raw JSON will eventually be wrapped in a <pre> tag by Chromium
                print("   ⏳ Waiting for Javascript redirect and JSON data to load...")
                try:
                    await page.wait_for_selector("pre", timeout=15000)
                except:
                    # If it fails to find 'pre', maybe we got blocked or are stuck on the login page forever
                    print("❌ [Tier 3] Failed to bypass redirect. Tor IP might be heavily blocked.")
                    self._rotate_tor_ip()
                    await browser.close()
                    await asyncio.sleep(5)
                    return False
                    
                content = await page.inner_text("pre")
                await browser.close()
                
                # Parse the JSON
                try:
                    data = json.loads(content)
                    for child in data['data']['children']:
                        p_data = child['data']
                        self.results.append({
                            "id": p_data.get('id'),
                            "title": p_data.get('title'),
                            "author": p_data.get('author'),
                            "permalink": p_data.get('permalink'),
                            "url": p_data.get('url'),
                            "score": p_data.get('score'),
                            "created_utc": p_data.get('created_utc'),
                            "source": "Tier3_Tor_Headless"
                        })
                        self.total_fetched += 1
                    print("   ✅ Tor Headless extraction successful!")
                    self.after = data['data'].get('after')
                    return True
                except json.JSONDecodeError:
                    print("❌ [Tier 3] Received content was not valid JSON.")
                    self._rotate_tor_ip()
                    await asyncio.sleep(5)
                    return False
                    
        except Exception as e:
            print(f"❌ [Tier 3] Playwright Error (Is Tor running on port {TOR_PORT}?): {e}")
            await asyncio.sleep(10)
            return False

    async def run(self):
        mode_str = "Global Search" if self.is_search else ("User" if self.is_user else "Subreddit")
        print(f"🚀 Starting 3-Tier Waterfall Scraper for {mode_str}: '{self.target}'")
        print(f"   Target: {self.limit} items")
        print("-" * 50)
        
        while self.total_fetched < self.limit:
            if self.current_tier == 1:
                success = await self.fetch_tier_1_praw()
                if success:
                    pass # PRAW handles pagination internally
            elif self.current_tier == 2:
                success = await self.fetch_tier_2_proxy()
                if not success:
                    pass
            elif self.current_tier == 3:
                success = await self.fetch_tier_3_tor()
                
            print(f"📊 Progress: {self.total_fetched} / {self.limit} items fetched")
            
            # Break if we hit the limit or if there's no more data to paginate
            if self.total_fetched >= self.limit or (success and self.current_tier != 1 and not self.after):
                if self.total_fetched < self.limit:
                    print("🏁 Reached the end of available Reddit history for this query.")
                break
                
        print("\n" + "=" * 50)
        print(f"✅ 3-Tier Scrape Complete! Fetched {len(self.results)} items.")
        return self.results

def run_3_tier_scraper(target, limit=100, is_user=False, is_search=False):
    scraper = TieredScraper(target, limit, is_user, is_search)
    return asyncio.run(scraper.run())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    
    results = run_3_tier_scraper(args.target, args.limit)
    print(f"Sample data: {results[:1]}")
