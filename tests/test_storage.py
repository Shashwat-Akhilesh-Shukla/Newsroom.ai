"""
Comprehensive tests for the storage layer.

Tests database operations, caching, and integration.
"""

import os
import sys
import time
import logging
from pathlib import Path
import tempfile
import shutil

# Add storage directory to path to import modules directly
# This avoids importing src/__init__.py which requires langgraph
project_root = Path(__file__).parent.parent
storage_path = project_root / "src" / "storage"
sys.path.insert(0, str(storage_path))

# Import storage modules directly
from database import (
    DatabaseManager,
    get_database,
    Topic,
    Research,
    Draft,
    Feedback,
    Publication
)

from cache import (
    CacheManager,
    get_cache,
    cache_result
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class TestDatabase:
    """Test database operations."""
    
    def __init__(self):
        # Use temporary database for testing
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_newsroom.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}", echo=False)
    
    def cleanup(self):
        """Clean up test database."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_topic(self):
        """Test creating a topic."""
        logger.info("Testing topic creation...")
        
        topic = self.db.create_topic(
            title="AI Breakthrough in Quantum Computing",
            confidence=0.85,
            metadata={"source": "HackerNews", "score": 150}
        )
        
        assert topic.topic_id is not None
        assert topic.title == "AI Breakthrough in Quantum Computing"
        assert topic.confidence == 0.85
        assert topic.status == "discovered"
        
        logger.info(f"✓ Topic created: {topic}")
        return topic
    
    def test_get_topic(self, topic_id):
        """Test retrieving a topic."""
        logger.info(f"Testing topic retrieval (ID={topic_id})...")
        
        topic = self.db.get_topic(topic_id)
        
        assert topic is not None
        assert topic.topic_id == topic_id
        
        logger.info(f"✓ Topic retrieved: {topic}")
        return topic
    
    def test_update_topic_status(self, topic_id):
        """Test updating topic status."""
        logger.info(f"Testing topic status update (ID={topic_id})...")
        
        success = self.db.update_topic_status(topic_id, "researching")
        assert success is True
        
        topic = self.db.get_topic(topic_id)
        assert topic.status == "researching"
        
        logger.info(f"✓ Topic status updated to: {topic.status}")
    
    def test_create_research(self, topic_id):
        """Test creating research notes."""
        logger.info(f"Testing research creation (topic_id={topic_id})...")
        
        research = self.db.create_research(
            topic_id=topic_id,
            source="ArXiv",
            content="Detailed research about quantum error correction...",
            citations=[
                {"title": "Paper 1", "url": "https://arxiv.org/1234"},
                {"title": "Paper 2", "url": "https://arxiv.org/5678"}
            ],
            metadata={"credibility": 0.9}
        )
        
        assert research.research_id is not None
        assert research.topic_id == topic_id
        assert len(research.citations) == 2
        
        logger.info(f"✓ Research created: {research}")
        return research
    
    def test_get_research_by_topic(self, topic_id):
        """Test retrieving research by topic."""
        logger.info(f"Testing research retrieval (topic_id={topic_id})...")
        
        research_list = self.db.get_research_by_topic(topic_id)
        
        assert len(research_list) > 0
        assert all(r.topic_id == topic_id for r in research_list)
        
        logger.info(f"✓ Retrieved {len(research_list)} research notes")
        return research_list
    
    def test_create_draft(self, topic_id):
        """Test creating a draft."""
        logger.info(f"Testing draft creation (topic_id={topic_id})...")
        
        draft_content = """# Quantum Computing Breakthrough

Recent advances in quantum error correction have brought us closer to practical quantum computers.

## The Challenge

Quantum computers are extremely sensitive to errors...

## The Solution

Researchers have developed a new error correction code..."""
        
        draft = self.db.create_draft(
            topic_id=topic_id,
            content=draft_content,
            version=1,
            metadata={"author": "WriterAgent"}
        )
        
        assert draft.draft_id is not None
        assert draft.topic_id == topic_id
        assert draft.version == 1
        assert draft.word_count > 0
        
        logger.info(f"✓ Draft created: {draft} ({draft.word_count} words)")
        return draft
    
    def test_get_latest_draft(self, topic_id):
        """Test retrieving latest draft."""
        logger.info(f"Testing latest draft retrieval (topic_id={topic_id})...")
        
        draft = self.db.get_latest_draft(topic_id)
        
        assert draft is not None
        assert draft.topic_id == topic_id
        
        logger.info(f"✓ Latest draft retrieved: version {draft.version}")
        return draft
    
    def test_create_feedback(self):
        """Test creating feedback."""
        logger.info("Testing feedback creation...")
        
        feedback = self.db.create_feedback(
            agent="skeptic",
            target_agent="researcher",
            content="Need more evidence for the 50% overhead reduction claim.",
            decision="NEED_MORE_EVIDENCE",
            metadata={"severity": "high"}
        )
        
        assert feedback.feedback_id is not None
        assert feedback.agent == "skeptic"
        assert feedback.decision == "NEED_MORE_EVIDENCE"
        
        logger.info(f"✓ Feedback created: {feedback}")
        return feedback
    
    def test_create_publication(self, topic_id, draft_id):
        """Test creating publication."""
        logger.info(f"Testing publication creation (topic_id={topic_id})...")
        
        publication = self.db.create_publication(
            topic_id=topic_id,
            draft_id=draft_id,
            platform="local",
            url=f"file:///output/article_{topic_id}.md",
            metadata={"keywords": ["quantum", "computing", "AI"]}
        )
        
        assert publication.pub_id is not None
        assert publication.topic_id == topic_id
        
        logger.info(f"✓ Publication created: {publication}")
        return publication
    
    def test_workflow_history(self, topic_id):
        """Test retrieving complete workflow history."""
        logger.info(f"Testing workflow history (topic_id={topic_id})...")
        
        history = self.db.get_workflow_history(topic_id)
        
        assert 'topic' in history
        assert 'research' in history
        assert 'drafts' in history
        assert 'feedback' in history
        assert 'publications' in history
        
        logger.info(f"✓ Workflow history retrieved:")
        logger.info(f"  - Research notes: {len(history['research'])}")
        logger.info(f"  - Drafts: {len(history['drafts'])}")
        logger.info(f"  - Feedback: {len(history['feedback'])}")
        logger.info(f"  - Publications: {len(history['publications'])}")
        
        return history
    
    def run_all_tests(self):
        """Run all database tests."""
        logger.info("=" * 60)
        logger.info("DATABASE TESTS")
        logger.info("=" * 60)
        
        try:
            # Test topic operations
            topic = self.test_create_topic()
            self.test_get_topic(topic.topic_id)
            self.test_update_topic_status(topic.topic_id)
            
            # Test research operations
            research = self.test_create_research(topic.topic_id)
            self.test_get_research_by_topic(topic.topic_id)
            
            # Test draft operations
            draft = self.test_create_draft(topic.topic_id)
            self.test_get_latest_draft(topic.topic_id)
            
            # Test feedback operations
            self.test_create_feedback()
            
            # Test publication operations
            self.test_create_publication(topic.topic_id, draft.draft_id)
            
            # Test workflow history
            self.test_workflow_history(topic.topic_id)
            
            logger.info("\n✅ All database tests passed!")
            return True
            
        except AssertionError as e:
            logger.error(f"\n❌ Database test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"\n❌ Database test error: {e}", exc_info=True)
            return False
        finally:
            self.cleanup()


class TestCache:
    """Test cache operations."""
    
    def __init__(self):
        self.cache = CacheManager(max_size=100, default_ttl=60)
    
    def test_llm_caching(self):
        """Test LLM response caching."""
        logger.info("Testing LLM response caching...")
        
        model = "gpt-4"
        prompt = "What is quantum computing?"
        response = "Quantum computing is a type of computation that harnesses quantum mechanics..."
        
        # Cache the response
        self.cache.cache_llm_response(model, prompt, response)
        
        # Retrieve from cache
        cached = self.cache.get_llm_response(model, prompt)
        
        assert cached == response
        logger.info("✓ LLM response cached and retrieved")
    
    def test_api_caching(self):
        """Test API response caching."""
        logger.info("Testing API response caching...")
        
        service = "hackernews"
        endpoint = "/topstories"
        params = {"limit": 10}
        response = {"stories": [1, 2, 3, 4, 5]}
        
        # Cache the response
        self.cache.cache_api_response(service, endpoint, params, response)
        
        # Retrieve from cache
        cached = self.cache.get_api_response(service, endpoint, params)
        
        assert cached == response
        logger.info("✓ API response cached and retrieved")
    
    def test_ttl_expiration(self):
        """Test TTL expiration."""
        logger.info("Testing TTL expiration...")
        
        # Create cache with 1-second TTL
        short_cache = CacheManager(max_size=10, default_ttl=1)
        
        # Cache something
        short_cache.cache_llm_response("model", "prompt", "response")
        
        # Should be in cache
        cached = short_cache.get_llm_response("model", "prompt")
        assert cached == "response"
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        cached = short_cache.get_llm_response("model", "prompt")
        assert cached is None
        
        logger.info("✓ TTL expiration working correctly")
    
    def test_lru_eviction(self):
        """Test LRU eviction."""
        logger.info("Testing LRU eviction...")
        
        # Create small cache
        small_cache = CacheManager(max_size=3, default_ttl=None)
        
        # Fill cache
        small_cache.cache.set("key1", "value1")
        small_cache.cache.set("key2", "value2")
        small_cache.cache.set("key3", "value3")
        
        # Add one more (should evict key1)
        small_cache.cache.set("key4", "value4")
        
        # key1 should be evicted
        assert small_cache.cache.get("key1") is None
        assert small_cache.cache.get("key4") == "value4"
        
        logger.info("✓ LRU eviction working correctly")
    
    def test_cache_stats(self):
        """Test cache statistics."""
        logger.info("Testing cache statistics...")
        
        # Perform some operations
        self.cache.cache_llm_response("model1", "prompt1", "response1")
        self.cache.get_llm_response("model1", "prompt1")  # Hit
        self.cache.get_llm_response("model2", "prompt2")  # Miss
        
        stats = self.cache.get_stats()
        
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'hit_rate' in stats
        
        logger.info(f"✓ Cache stats: {stats}")
    
    def test_invalidation(self):
        """Test cache invalidation."""
        logger.info("Testing cache invalidation...")
        
        # Cache some data
        self.cache.cache_research(123, {"data": "research"})
        
        # Verify it's cached
        assert self.cache.get_research(123) is not None
        
        # Invalidate
        self.cache.invalidate_topic(123)
        
        # Should be gone
        assert self.cache.get_research(123) is None
        
        logger.info("✓ Cache invalidation working correctly")
    
    def test_decorator(self):
        """Test cache_result decorator."""
        logger.info("Testing cache_result decorator...")
        
        call_count = [0]
        
        @cache_result(ttl=60, key_prefix='test')
        def expensive_function(x, y):
            call_count[0] += 1
            return x ** y
        
        # First call - should execute
        result1 = expensive_function(2, 10)
        assert result1 == 1024
        assert call_count[0] == 1
        
        # Second call - should use cache
        result2 = expensive_function(2, 10)
        assert result2 == 1024
        assert call_count[0] == 1  # Not incremented
        
        logger.info("✓ cache_result decorator working correctly")
    
    def run_all_tests(self):
        """Run all cache tests."""
        logger.info("\n" + "=" * 60)
        logger.info("CACHE TESTS")
        logger.info("=" * 60)
        
        try:
            self.test_llm_caching()
            self.test_api_caching()
            self.test_ttl_expiration()
            self.test_lru_eviction()
            self.test_cache_stats()
            self.test_invalidation()
            self.test_decorator()
            
            logger.info("\n✅ All cache tests passed!")
            return True
            
        except AssertionError as e:
            logger.error(f"\n❌ Cache test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"\n❌ Cache test error: {e}", exc_info=True)
            return False


def main():
    """Run all storage tests."""
    logger.info("\n" + "=" * 60)
    logger.info("AI NEWSROOM - Storage Layer Tests")
    logger.info("=" * 60)
    
    results = {}
    
    # Test database
    db_tests = TestDatabase()
    results['database'] = db_tests.run_all_tests()
    
    # Test cache
    cache_tests = TestCache()
    results['cache'] = cache_tests.run_all_tests()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name.capitalize()}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✅ All storage layer tests passed!")
        logger.info("Storage layer is ready for integration.")
    else:
        logger.error("\n❌ Some tests failed!")
        logger.error("Review the logs above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
