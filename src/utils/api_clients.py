"""
API clients for external services.

This module provides async clients for fetching data from various external sources:
- Hacker News: Top stories and discussions
- ArXiv: Academic papers
- Google Trends: Search trends
- Reddit: Hot/trending posts from tech subreddits
- DuckDuckGo News: Trending news articles via DuckDuckGo search

Each client includes rate limiting, retry logic, and error handling.
"""

import asyncio
import logging
import httpx
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# ============================================================================
# Utility Decorators
# ============================================================================

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying async functions with exponential backoff.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
            
        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
    
    async def wait(self):
        """Wait asynchronously if necessary to respect rate limit."""
        current_time = asyncio.get_event_loop().time()
        time_since_last_call = current_time - self.last_call
        
        if time_since_last_call < self.min_interval:
            sleep_time = self.min_interval - time_since_last_call
            await asyncio.sleep(sleep_time)
            
        self.last_call = asyncio.get_event_loop().time()


# ============================================================================
# Hacker News Client
# ============================================================================

class HackerNewsClient:
    """Client for Hacker News API."""
    
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    
    def __init__(self):
        self.rate_limiter = RateLimiter(calls_per_second=2.0)
        self.session = httpx.AsyncClient(headers={'User-Agent': 'AI-Newsroom/1.0'})
    
    @retry_with_backoff(max_retries=3)
    async def _make_request(self, endpoint: str) -> Any:
        await self.rate_limiter.wait()
        response = await self.session.get(f"{self.BASE_URL}/{endpoint}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    
    async def get_top_stories(self, limit: int = 30) -> List[int]:
        try:
            story_ids = await self._make_request("topstories.json")
            return story_ids[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch top stories: {e}")
            return []
    
    async def get_story_details(self, story_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self._make_request(f"item/{story_id}.json")
        except Exception as e:
            logger.error(f"Failed to fetch story {story_id}: {e}")
            return None
    
    async def get_trending_topics(self, limit: int = 30) -> List[Dict[str, Any]]:
        story_ids = await self.get_top_stories(limit)
        
        # Fetch details concurrently
        tasks = [self.get_story_details(sid) for sid in story_ids]
        stories = await asyncio.gather(*tasks, return_exceptions=True)
        
        topics = []
        for story, story_id in zip(stories, story_ids):
            if isinstance(story, dict) and story.get('type') == 'story':
                topics.append({
                    'title': story.get('title', ''),
                    'url': story.get('url', ''),
                    'score': story.get('score', 0),
                    'comments': story.get('descendants', 0),
                    'author': story.get('by', ''),
                    'time': story.get('time', 0),
                    'source': 'hackernews',
                    'id': story_id
                })
        
        topics.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"Fetched {len(topics)} trending topics from Hacker News")
        return topics


# ============================================================================
# ArXiv Client
# ============================================================================

class ArXivClient:
    """Client for ArXiv API."""
    
    BASE_URL = "https://export.arxiv.org/api/query"
    
    def __init__(self):
        self.rate_limiter = RateLimiter(calls_per_second=0.5)
        self.session = httpx.AsyncClient(headers={'User-Agent': 'AI-Newsroom/1.0'})
    
    @retry_with_backoff(max_retries=3)
    async def _make_request(self, params: Dict[str, Any]) -> str:
        await self.rate_limiter.wait()
        response = await self.session.get(self.BASE_URL, params=params, timeout=15.0)
        response.raise_for_status()
        return response.text
    
    async def search_papers(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            xml_data = await self._make_request(params)
            return self._parse_arxiv_response(xml_data)
            
        except Exception as e:
            logger.error(f"Failed to search ArXiv for '{query}': {e}")
            return []
    
    async def get_recent_papers(self, category: str = 'cs.AI', days: int = 7, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            params = {
                'search_query': f'cat:{category}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            xml_data = await self._make_request(params)
            papers = self._parse_arxiv_response(xml_data)
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            recent_papers = [
                p for p in papers 
                if datetime.fromisoformat(p['published'].replace('Z', '+00:00')) > cutoff_date
            ]
            
            logger.info(f"Fetched {len(recent_papers)} recent papers from {category}")
            return recent_papers
            
        except Exception as e:
            logger.error(f"Failed to fetch recent papers from {category}: {e}")
            return []
    
    def _parse_arxiv_response(self, xml_data: str) -> List[Dict[str, Any]]:
        papers = []
        try:
            root = ET.fromstring(xml_data)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', namespace):
                paper = {
                    'title': entry.find('atom:title', namespace).text.strip(),
                    'summary': entry.find('atom:summary', namespace).text.strip(),
                    'authors': [
                        author.find('atom:name', namespace).text 
                        for author in entry.findall('atom:author', namespace)
                    ],
                    'published': entry.find('atom:published', namespace).text,
                    'url': entry.find('atom:id', namespace).text,
                    'source': 'arxiv'
                }
                
                categories = entry.findall('atom:category', namespace)
                paper['categories'] = [cat.get('term') for cat in categories]
                papers.append(paper)
                
        except Exception as e:
            logger.error(f"Failed to parse ArXiv response: {e}")
        
        return papers


# ============================================================================
# Google Trends Client
# ============================================================================

class GoogleTrendsClient:
    """Client for Google Trends using pytrends library."""
    
    def __init__(self):
        try:
            from pytrends.request import TrendReq
            self.pytrends = TrendReq(hl='en-US', tz=360)
            self.available = True
        except ImportError:
            logger.warning("pytrends not installed. Google Trends functionality disabled.")
            self.available = False
    
    def _get_trending_searches_sync(self, region: str) -> List[Dict[str, Any]]:
        trending_df = self.pytrends.trending_searches(pn=region)
        trends = []
        for idx, keyword in enumerate(trending_df[0].head(20)):
            trends.append({
                'keyword': keyword,
                'rank': idx + 1,
                'source': 'google_trends',
                'region': region
            })
        return trends
        
    async def get_trending_searches(self, region: str = 'united_states') -> List[Dict[str, Any]]:
        if not self.available:
            return []
        try:
            trends = await asyncio.to_thread(self._get_trending_searches_sync, region)
            logger.info(f"Fetched {len(trends)} trending searches from Google Trends")
            return trends
        except Exception as e:
            logger.error(f"Failed to fetch trending searches: {e}")
            return []
    
    def _get_interest_over_time_sync(self, keywords: List[str], timeframe: str) -> Dict[str, Any]:
        self.pytrends.build_payload(keywords, timeframe=timeframe)
        interest_df = self.pytrends.interest_over_time()
        
        if interest_df.empty:
            return {}
        
        return {
            'keywords': keywords,
            'timeframe': timeframe,
            'data': interest_df.to_dict('records')
        }

    async def get_interest_over_time(self, keywords: List[str], timeframe: str = 'now 7-d') -> Dict[str, Any]:
        if not self.available or not keywords:
            return {}
        try:
            result = await asyncio.to_thread(self._get_interest_over_time_sync, keywords, timeframe)
            return result
        except Exception as e:
            logger.error(f"Failed to get interest over time: {e}")
            return {}


# ============================================================================
# Reddit Client (Free — no API key required for public JSON endpoints)
# ============================================================================

class RedditClient:
    SUBREDDITS = [
        "technology", "programming", "artificial", "MachineLearning",
        "science", "worldnews", "Futurology", "cybersecurity"
    ]
    BASE_URL = "https://www.reddit.com"

    def __init__(self):
        self.rate_limiter = RateLimiter(calls_per_second=0.5)
        self.session = httpx.AsyncClient(headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.reddit.com/",
            })

    @retry_with_backoff(max_retries=3)
    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        await self.rate_limiter.wait()
        response = await self.session.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()

    async def get_hot_posts(self, subreddit: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            url = f"{self.BASE_URL}/r/{subreddit}/hot.json"
            data = await self._make_request(url, params={'limit': limit, 'raw_json': 1})
            posts = []
            for child in data.get('data', {}).get('children', []):
                post = child.get('data', {})
                if post.get('stickied'):
                    continue
                posts.append({
                    'title': post.get('title', ''),
                    'url': post.get('url', ''),
                    'score': post.get('score', 0),
                    'comments': post.get('num_comments', 0),
                    'author': post.get('author', ''),
                    'subreddit': subreddit,
                    'permalink': f"https://www.reddit.com{post.get('permalink', '')}",
                    'source': 'reddit',
                })
            return posts
        except Exception as e:
            logger.error(f"Failed to fetch hot posts from r/{subreddit}: {e}")
            return []

    async def get_trending_topics(self, posts_per_subreddit: int = 10) -> List[Dict[str, Any]]:
        tasks = [self.get_hot_posts(subreddit, limit=posts_per_subreddit) for subreddit in self.SUBREDDITS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_posts = []
        for posts in results:
            if isinstance(posts, list):
                all_posts.extend(posts)

        seen_urls: Dict[str, Dict[str, Any]] = {}
        for post in all_posts:
            url = post.get('url', '')
            if not url:
                continue
            if url not in seen_urls or post['score'] > seen_urls[url]['score']:
                seen_urls[url] = post

        deduped = sorted(seen_urls.values(), key=lambda x: x['score'], reverse=True)
        logger.info(f"Fetched {len(deduped)} unique trending posts from Reddit")
        return deduped


# ============================================================================
# DuckDuckGo News Client (Free — no API key required)
# ============================================================================

class DuckDuckGoNewsClient:
    DDG_API_URL = "https://api.duckduckgo.com/"

    SEARCH_QUERIES = [
        "technology news",
        "artificial intelligence",
        "science discovery",
        "cybersecurity breach",
        "software engineering",
    ]

    def __init__(self):
        self.rate_limiter = RateLimiter(calls_per_second=0.3)
        self.session = httpx.AsyncClient(headers={
            'User-Agent': 'Mozilla/5.0 (compatible; AI-Newsroom/1.0)'
        })

    @retry_with_backoff(max_retries=3)
    async def _search_news(self, query: str) -> List[Dict[str, Any]]:
        await self.rate_limiter.wait()
        params = {
            'q': query,
            'format': 'json',
            'no_html': '1',
            'skip_disambig': '1',
        }
        try:
            resp = await self.session.get(self.DDG_API_URL, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"DuckDuckGo JSON API failed for '{query}': {e}")
            return []

        results = []
        for item in data.get('RelatedTopics', []):
            text = item.get('Text', '')
            url = item.get('FirstURL', '')
            if text and url:
                results.append({
                    'title': text[:200],
                    'url': url,
                    'query': query,
                    'source': 'duckduckgo_news',
                    'score': 0,
                })
            for sub in item.get('Topics', []):
                sub_text = sub.get('Text', '')
                sub_url = sub.get('FirstURL', '')
                if sub_text and sub_url:
                    results.append({
                        'title': sub_text[:200],
                        'url': sub_url,
                        'query': query,
                        'source': 'duckduckgo_news',
                        'score': 0,
                    })
        return results

    async def search_news(self, query: str) -> List[Dict[str, Any]]:
        """Public method to search news by query."""
        results = await self._search_news(query)
        # Deduplicate
        seen: Dict[str, Dict[str, Any]] = {}
        for item in results:
            url = item.get('url', '')
            if url and url not in seen:
                seen[url] = item
        return list(seen.values())

    async def get_trending_topics(self) -> List[Dict[str, Any]]:
        tasks = [self._search_news(query) for query in self.SEARCH_QUERIES]
        semaphore = asyncio.Semaphore(2)

        async def limited_task(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[limited_task(t) for t in tasks])
        
        all_results = []
        for r in results:
            if isinstance(r, list):
                all_results.extend(r)

        seen: Dict[str, Dict[str, Any]] = {}
        for item in all_results:
            url = item.get('url', '')
            if url and url not in seen:
                seen[url] = item

        deduped = list(seen.values())
        logger.info(f"Fetched {len(deduped)} unique results from DuckDuckGo News")
        return deduped


# ============================================================================
# Aggregator Client
# ============================================================================

class TrendAggregator:
    def __init__(self):
        self.hn_client = HackerNewsClient()
        self.arxiv_client = ArXivClient()
        self.trends_client = GoogleTrendsClient()
        self.reddit_client = RedditClient()
        self.ddg_client = DuckDuckGoNewsClient()

    async def get_all_trends(self, hn_limit: int = 30, arxiv_limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        logger.info("Fetching trends from all sources...")

        # Run queries concurrently
        hn_task = self.hn_client.get_trending_topics(limit=hn_limit)
        arxiv_task = self.arxiv_client.get_recent_papers(max_results=arxiv_limit)
        trends_task = self.trends_client.get_trending_searches()
        reddit_task = self.reddit_client.get_trending_topics()
        ddg_task = self.ddg_client.get_trending_topics()

        results = await asyncio.gather(
            hn_task, arxiv_task, trends_task, reddit_task, ddg_task,
            return_exceptions=True
        )

        def _safe_result(result):
            return result if isinstance(result, list) else []

        trends = {
            'hackernews': _safe_result(results[0]),
            'arxiv': _safe_result(results[1]),
            'google_trends': _safe_result(results[2]),
            'reddit': _safe_result(results[3]),
            'duckduckgo_news': _safe_result(results[4]),
        }

        total_trends = sum(len(v) for v in trends.values())
        success_sources = sum(1 for v in trends.values() if v)
        logger.info(f"Fetched {total_trends} total trends from {success_sources} sources")

        return trends
