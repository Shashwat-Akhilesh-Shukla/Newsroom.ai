"""
API clients for external services.

This module provides clients for fetching data from various external sources:
- Hacker News: Top stories and discussions
- ArXiv: Academic papers
- Google Trends: Search trends
- Reddit: Hot/trending posts from tech subreddits (free, no auth required)
- DuckDuckGo News: Trending news articles via DuckDuckGo search (free, no API key)

Each client includes rate limiting, retry logic, and error handling.
"""

import time
import logging
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from functools import wraps
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# ============================================================================
# Utility Decorators
# ============================================================================

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles with each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            
        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, calls_per_second: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_second: Maximum calls allowed per second
        """
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call
        
        if time_since_last_call < self.min_interval:
            sleep_time = self.min_interval - time_since_last_call
            time.sleep(sleep_time)
        
        self.last_call = time.time()


# ============================================================================
# Hacker News Client
# ============================================================================

class HackerNewsClient:
    """Client for Hacker News API."""
    
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    
    def __init__(self):
        """Initialize Hacker News client."""
        self.rate_limiter = RateLimiter(calls_per_second=2.0)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AI-Newsroom/1.0'})
    
    @retry_with_backoff(max_retries=3)
    def _make_request(self, endpoint: str) -> Any:
        """Make a request to the HN API with rate limiting."""
        self.rate_limiter.wait()
        response = self.session.get(f"{self.BASE_URL}/{endpoint}")
        response.raise_for_status()
        return response.json()
    
    def get_top_stories(self, limit: int = 30) -> List[int]:
        """
        Get top story IDs from Hacker News.
        
        Args:
            limit: Maximum number of story IDs to return
            
        Returns:
            List of story IDs
        """
        try:
            story_ids = self._make_request("topstories.json")
            return story_ids[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch top stories: {e}")
            return []
    
    def get_story_details(self, story_id: int) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific story.
        
        Args:
            story_id: Story ID
            
        Returns:
            Story details or None if not found
        """
        try:
            return self._make_request(f"item/{story_id}.json")
        except Exception as e:
            logger.error(f"Failed to fetch story {story_id}: {e}")
            return None
    
    def get_trending_topics(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Get trending topics from Hacker News.
        
        Args:
            limit: Maximum number of topics to return
            
        Returns:
            List of trending topics with metadata
        """
        story_ids = self.get_top_stories(limit)
        topics = []
        
        for story_id in story_ids:
            story = self.get_story_details(story_id)
            if story and story.get('type') == 'story':
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
        
        # Sort by score (engagement)
        topics.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"Fetched {len(topics)} trending topics from Hacker News")
        return topics


# ============================================================================
# ArXiv Client
# ============================================================================

class ArXivClient:
    """Client for ArXiv API."""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self):
        """Initialize ArXiv client."""
        self.rate_limiter = RateLimiter(calls_per_second=0.5)  # ArXiv prefers slower rate
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AI-Newsroom/1.0'})
    
    @retry_with_backoff(max_retries=3)
    def _make_request(self, params: Dict[str, Any]) -> str:
        """Make a request to the ArXiv API with rate limiting."""
        self.rate_limiter.wait()
        response = self.session.get(self.BASE_URL, params=params)
        response.raise_for_status()
        return response.text
    
    def search_papers(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for papers on ArXiv.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of paper metadata
        """
        try:
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            xml_data = self._make_request(params)
            return self._parse_arxiv_response(xml_data)
            
        except Exception as e:
            logger.error(f"Failed to search ArXiv for '{query}': {e}")
            return []
    
    def get_recent_papers(self, category: str = 'cs.AI', days: int = 7, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent papers from a specific category.
        
        Args:
            category: ArXiv category (e.g., 'cs.AI', 'cs.LG')
            days: Number of days to look back
            max_results: Maximum number of results
            
        Returns:
            List of paper metadata
        """
        try:
            params = {
                'search_query': f'cat:{category}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            xml_data = self._make_request(params)
            papers = self._parse_arxiv_response(xml_data)
            
            # Filter by date
            cutoff_date = datetime.now() - timedelta(days=days)
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
        """Parse ArXiv XML response."""
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
                
                # Extract categories
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
        """Initialize Google Trends client."""
        try:
            from pytrends.request import TrendReq
            self.pytrends = TrendReq(hl='en-US', tz=360)
            self.available = True
        except ImportError:
            logger.warning("pytrends not installed. Google Trends functionality disabled.")
            self.available = False
    
    def get_trending_searches(self, region: str = 'united_states') -> List[Dict[str, Any]]:
        """
        Get trending searches from Google Trends.
        
        Args:
            region: Region code (e.g., 'united_states', 'united_kingdom')
            
        Returns:
            List of trending searches
        """
        if not self.available:
            return []
        
        try:
            from pytrends.request import TrendReq
            
            # Get trending searches
            trending_df = self.pytrends.trending_searches(pn=region)
            
            trends = []
            for idx, keyword in enumerate(trending_df[0].head(20)):
                trends.append({
                    'keyword': keyword,
                    'rank': idx + 1,
                    'source': 'google_trends',
                    'region': region
                })
            
            logger.info(f"Fetched {len(trends)} trending searches from Google Trends")
            return trends
            
        except Exception as e:
            logger.error(f"Failed to fetch trending searches: {e}")
            return []
    
    def get_interest_over_time(self, keywords: List[str], timeframe: str = 'now 7-d') -> Dict[str, Any]:
        """
        Get interest over time for keywords.
        
        Args:
            keywords: List of keywords to analyze
            timeframe: Time frame (e.g., 'now 7-d', 'today 3-m')
            
        Returns:
            Interest data
        """
        if not self.available or not keywords:
            return {}
        
        try:
            self.pytrends.build_payload(keywords, timeframe=timeframe)
            interest_df = self.pytrends.interest_over_time()
            
            if interest_df.empty:
                return {}
            
            # Convert to dict format
            result = {
                'keywords': keywords,
                'timeframe': timeframe,
                'data': interest_df.to_dict('records')
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get interest over time: {e}")
            return {}


# ============================================================================
# Reddit Client (Free — no API key required for public JSON endpoints)
# ============================================================================

class RedditClient:
    """
    Client for Reddit's public JSON API.

    Uses Reddit's unauthenticated JSON endpoints (no API key needed).
    Fetches hot posts from a curated list of tech/science subreddits.
    """

    SUBREDDITS = [
        "technology", "programming", "artificial", "MachineLearning",
        "science", "worldnews", "Futurology", "cybersecurity"
    ]
    BASE_URL = "https://www.reddit.com"

    def __init__(self):
        """Initialize Reddit client."""
        self.rate_limiter = RateLimiter(calls_per_second=0.5)  # be polite to Reddit
        self.session = requests.Session()
        # Reddit requires a non-default User-Agent to avoid 429s
        self.session.headers.update({
            'User-Agent': 'AI-Newsroom/1.0 (trend aggregator; contact: newsroom@example.com)'
        })

    @retry_with_backoff(max_retries=3)
    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a request to the Reddit JSON API with rate limiting."""
        self.rate_limiter.wait()
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_hot_posts(self, subreddit: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get hot posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/)
            limit: Maximum number of posts to return

        Returns:
            List of post metadata dicts
        """
        try:
            url = f"{self.BASE_URL}/r/{subreddit}/hot.json"
            data = self._make_request(url, params={'limit': limit, 'raw_json': 1})
            posts = []
            for child in data.get('data', {}).get('children', []):
                post = child.get('data', {})
                # Skip pinned/stickied mod posts
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

    def get_trending_topics(self, posts_per_subreddit: int = 10) -> List[Dict[str, Any]]:
        """
        Aggregate hot posts from all tracked subreddits.

        Args:
            posts_per_subreddit: How many hot posts to pull per subreddit

        Returns:
            Combined list of trending posts sorted by score
        """
        all_posts: List[Dict[str, Any]] = []
        for subreddit in self.SUBREDDITS:
            posts = self.get_hot_posts(subreddit, limit=posts_per_subreddit)
            all_posts.extend(posts)

        # Deduplicate by URL, keep highest-score entry
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
    """
    Fetches trending news headlines via DuckDuckGo's news search endpoint.

    Uses the unofficial DuckDuckGo news JSON endpoint — no API key required.
    Searches for broad tech/AI/science news to surface trending topics.
    """

    DDG_NEWS_URL = "https://duckduckgo.com/"
    DDG_API_URL = "https://api.duckduckgo.com/"

    SEARCH_QUERIES = [
        "technology news",
        "artificial intelligence",
        "science discovery",
        "cybersecurity breach",
        "software engineering",
    ]

    def __init__(self):
        """Initialize DuckDuckGo News client."""
        self.rate_limiter = RateLimiter(calls_per_second=0.3)  # gentle rate limiting
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; AI-Newsroom/1.0)'
        })

    @retry_with_backoff(max_retries=3)
    def _search_news(self, query: str) -> List[Dict[str, Any]]:
        """
        Search news for a given query using DuckDuckGo's JSON API.

        Args:
            query: Search term

        Returns:
            List of news result dicts
        """
        self.rate_limiter.wait()
        params = {
            'q': query,
            'format': 'json',
            'no_html': '1',
            'skip_disambig': '1',
        }
        try:
            resp = self.session.get(self.DDG_API_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"DuckDuckGo JSON API failed for '{query}': {e}")
            return []

        results = []
        # RelatedTopics carry news-like snippets
        for item in data.get('RelatedTopics', []):
            # Flat items have 'Text' and 'FirstURL'
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
            # subs inside 'Topics'
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

    def get_trending_topics(self) -> List[Dict[str, Any]]:
        """
        Get trending topics by running multiple topic searches on DuckDuckGo.

        Returns:
            Combined, deduplicated list of news results
        """
        all_results: List[Dict[str, Any]] = []
        for query in self.SEARCH_QUERIES:
            results = self._search_news(query)
            all_results.extend(results)

        # Deduplicate by URL
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
    """Aggregates trends from multiple sources."""

    def __init__(self):
        """
        Initialize trend aggregator with all clients.
        All sources are free and require no API keys.
        """
        self.hn_client = HackerNewsClient()
        self.arxiv_client = ArXivClient()
        self.trends_client = GoogleTrendsClient()
        self.reddit_client = RedditClient()
        self.ddg_client = DuckDuckGoNewsClient()

    def get_all_trends(self, hn_limit: int = 30, arxiv_limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch trends from all available sources.

        Args:
            hn_limit: Number of HN stories to fetch
            arxiv_limit: Number of ArXiv papers to fetch

        Returns:
            Dictionary with trends from each source
        """
        logger.info("Fetching trends from all sources...")

        trends = {
            'hackernews': self.hn_client.get_trending_topics(limit=hn_limit),
            'arxiv': self.arxiv_client.get_recent_papers(max_results=arxiv_limit),
            'google_trends': self.trends_client.get_trending_searches(),
            'reddit': self.reddit_client.get_trending_topics(),
            'duckduckgo_news': self.ddg_client.get_trending_topics(),
        }

        total_trends = sum(len(v) for v in trends.values())
        logger.info(
            f"Fetched {total_trends} total trends from "
            f"{len([k for k, v in trends.items() if v])} sources"
        )

        return trends
