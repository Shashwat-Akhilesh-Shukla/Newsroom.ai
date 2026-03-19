"""
Database layer for persistent storage.

Implements SQLAlchemy models and database operations for the AI Newsroom.
Uses PostgreSQL as the database backend (via asyncpg).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON, select, delete
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Support both SQLAlchemy 1.x and 2.x
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()

# Default PostgreSQL URL (override via DATABASE_URL env var)
_DEFAULT_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/newsroom"


# Models

class Topic(Base):
    """Topic discovered by Scout agent."""
    __tablename__ = 'topics'
    
    topic_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(50), default='discovered')  # discovered, researching, approved, rejected, published
    meta_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    research_notes = relationship("Research", back_populates="topic", cascade="all, delete-orphan")
    drafts = relationship("Draft", back_populates="topic", cascade="all, delete-orphan")
    publications = relationship("Publication", back_populates="topic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Topic(id={self.topic_id}, title='{self.title[:50]}...', confidence={self.confidence})>"


class Research(Base):
    """Research notes gathered by Researcher agent."""
    __tablename__ = 'research'
    
    research_id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey('topics.topic_id'), nullable=False)
    source = Column(String(200), nullable=False)  # HackerNews, ArXiv, etc.
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)  # List of citation dicts
    meta_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    topic = relationship("Topic", back_populates="research_notes")
    
    def __repr__(self):
        return f"<Research(id={self.research_id}, topic_id={self.topic_id}, source='{self.source}')>"


class Draft(Base):
    """Article drafts created by Writer agent."""
    __tablename__ = 'drafts'
    
    draft_id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey('topics.topic_id'), nullable=False)
    version = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    status = Column(String(50), default='draft')  # draft, under_review, approved, rejected
    word_count = Column(Integer, default=0)
    meta_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    topic = relationship("Topic", back_populates="drafts")
    
    def __repr__(self):
        return f"<Draft(id={self.draft_id}, topic_id={self.topic_id}, version={self.version}, status='{self.status}')>"


class Feedback(Base):
    """Feedback between agents (Skeptic, Editor, etc.)."""
    __tablename__ = 'feedback'
    
    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    agent = Column(String(50), nullable=False)  # skeptic, editor, publisher
    target_agent = Column(String(50), nullable=False)  # scout, researcher, writer
    content = Column(Text, nullable=False)
    decision = Column(String(50))  # APPROVE, REJECT, NEED_MORE_EVIDENCE, REWRITE, etc.
    meta_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Feedback(id={self.feedback_id}, {self.agent}->{self.target_agent}, decision='{self.decision}')>"


class Publication(Base):
    """Published articles."""
    __tablename__ = 'publications'
    
    pub_id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey('topics.topic_id'), nullable=False)
    draft_id = Column(Integer, ForeignKey('drafts.draft_id'), nullable=True)
    platform = Column(String(100), default='local')  # local, medium, dev.to, etc.
    url = Column(String(500), nullable=True)
    meta_data = Column(JSON, default=dict)  # SEO data, keywords, etc.
    published_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    topic = relationship("Topic", back_populates="publications")
    
    def __repr__(self):
        return f"<Publication(id={self.pub_id}, topic_id={self.topic_id}, platform='{self.platform}')>"


# Database Manager

class DatabaseManager:
    """
    Manages async database connections and operations.

    Uses PostgreSQL as the backend via asyncpg. The connection URL is resolved in this order:
      1. ``db_url`` argument passed to the constructor
      2. ``DATABASE_URL`` environment variable
      3. Hard-coded default: ``postgresql+asyncpg://postgres:postgres@localhost:5432/newsroom``
    """

    def __init__(self, db_url: Optional[str] = None, echo: bool = False):
        if db_url is None:
            db_url = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

        if not db_url.startswith("postgresql+asyncpg"):
            raise ValueError(
                f"Only asyncpg is supported. Got URL scheme: {db_url.split('://')[0]!r}. "
                "Set DATABASE_URL to a postgresql+asyncpg:// connection string."
            )

        logger.info(f"Connecting to PostgreSQL (async): {db_url.split('@')[-1]}")

        self.engine = create_async_engine(
            db_url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

        self.SessionLocal = async_sessionmaker(bind=self.engine, expire_on_commit=False, class_=AsyncSession)
        
    async def initialize_db(self):
        """Create all tables if they don't exist asynchronously."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.debug("Database tables created/verified")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """Get a database session (async context manager)."""
        async with self.SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise

    # CRUD Operations for Topic
    
    async def create_topic(self, title: str, confidence: float, meta_data: Optional[Dict] = None) -> Topic:
        async with self.get_session() as session:
            topic = Topic(title=title, confidence=confidence, meta_data=meta_data or {})
            session.add(topic)
            await session.flush()
            await session.refresh(topic)
            logger.info(f"Created topic: {topic}")
            return topic
    
    async def get_topic(self, topic_id: int) -> Optional[Topic]:
        async with self.get_session() as session:
            result = await session.execute(select(Topic).filter(Topic.topic_id == topic_id))
            return result.scalars().first()
    
    async def update_topic_status(self, topic_id: int, status: str) -> bool:
        async with self.get_session() as session:
            result = await session.execute(select(Topic).filter(Topic.topic_id == topic_id))
            topic = result.scalars().first()
            if topic:
                topic.status = status
                topic.updated_at = datetime.utcnow()
                logger.info(f"Updated topic {topic_id} status to: {status}")
                return True
            return False
    
    async def get_topics_by_status(self, status: str) -> List[Topic]:
        async with self.get_session() as session:
            result = await session.execute(select(Topic).filter(Topic.status == status))
            return list(result.scalars().all())
    
    # CRUD Operations for Research
    
    async def create_research(self, topic_id: int, source: str, content: str, 
                       citations: Optional[List[Dict]] = None, meta_data: Optional[Dict] = None) -> Research:
        async with self.get_session() as session:
            research = Research(
                topic_id=topic_id, source=source, content=content,
                citations=citations or [], meta_data=meta_data or {}
            )
            session.add(research)
            await session.flush()
            await session.refresh(research)
            logger.info(f"Created research note: {research}")
            return research
    
    async def get_research_by_topic(self, topic_id: int) -> List[Research]:
        async with self.get_session() as session:
            result = await session.execute(select(Research).filter(Research.topic_id == topic_id))
            return list(result.scalars().all())
    
    # CRUD Operations for Draft
    
    async def create_draft(self, topic_id: int, content: str, version: int = 1,
                    meta_data: Optional[Dict] = None) -> Draft:
        word_count = len(content.split())
        async with self.get_session() as session:
            draft = Draft(
                topic_id=topic_id, version=version, content=content,
                word_count=word_count, meta_data=meta_data or {}
            )
            session.add(draft)
            await session.flush()
            await session.refresh(draft)
            logger.info(f"Created draft: {draft}")
            return draft
    
    async def get_latest_draft(self, topic_id: int) -> Optional[Draft]:
        async with self.get_session() as session:
            result = await session.execute(
                select(Draft).filter(Draft.topic_id == topic_id).order_by(Draft.version.desc())
            )
            return result.scalars().first()
    
    async def get_drafts_by_topic(self, topic_id: int) -> List[Draft]:
        async with self.get_session() as session:
            result = await session.execute(
                select(Draft).filter(Draft.topic_id == topic_id).order_by(Draft.version)
            )
            return list(result.scalars().all())
    
    # CRUD Operations for Feedback
    
    async def create_feedback(self, agent: str, target_agent: str, content: str,
                       decision: Optional[str] = None, meta_data: Optional[Dict] = None) -> Feedback:
        async with self.get_session() as session:
            feedback = Feedback(
                agent=agent, target_agent=target_agent, content=content,
                decision=decision, meta_data=meta_data or {}
            )
            session.add(feedback)
            await session.flush()
            await session.refresh(feedback)
            logger.info(f"Created feedback: {feedback}")
            return feedback
    
    async def get_feedback_by_agent(self, agent: str) -> List[Feedback]:
        async with self.get_session() as session:
            result = await session.execute(select(Feedback).filter(Feedback.agent == agent))
            return list(result.scalars().all())
    
    # CRUD Operations for Publication
    
    async def create_publication(self, topic_id: int, draft_id: Optional[int] = None,
                          platform: str = 'local', url: Optional[str] = None,
                          meta_data: Optional[Dict] = None) -> Publication:
        async with self.get_session() as session:
            publication = Publication(
                topic_id=topic_id, draft_id=draft_id, platform=platform,
                url=url, meta_data=meta_data or {}
            )
            session.add(publication)
            await session.flush()
            await session.refresh(publication)
            logger.info(f"Created publication: {publication}")
            return publication
    
    async def get_publications(self, platform: Optional[str] = None) -> List[Publication]:
        async with self.get_session() as session:
            query = select(Publication)
            if platform:
                query = query.filter(Publication.platform == platform)
            result = await session.execute(query)
            return list(result.scalars().all())
    
    # Utility Methods
    
    async def get_workflow_history(self, topic_id: int) -> Dict[str, Any]:
        async with self.get_session() as session:
            topic_result = await session.execute(select(Topic).filter(Topic.topic_id == topic_id))
            topic = topic_result.scalars().first()
            if not topic:
                return {}
            
            research_result = await session.execute(select(Research).filter(Research.topic_id == topic_id))
            drafts_result = await session.execute(select(Draft).filter(Draft.topic_id == topic_id).order_by(Draft.version))
            feedback_result = await session.execute(select(Feedback))
            pubs_result = await session.execute(select(Publication).filter(Publication.topic_id == topic_id))
            
            return {
                'topic': topic,
                'research': list(research_result.scalars().all()),
                'drafts': list(drafts_result.scalars().all()),
                'feedback': list(feedback_result.scalars().all()),
                'publications': list(pubs_result.scalars().all())
            }
    
    async def cleanup_old_data(self, days: int = 30):
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        async with self.get_session() as session:
            result = await session.execute(
                delete(Topic).where((Topic.created_at < cutoff_date) & (Topic.status != 'published'))
            )
            logger.info(f"Cleaned up old topics")


# Global database instance (lazy initialization)
_db_instance: Optional[DatabaseManager] = None


def get_database(db_url: Optional[str] = None, echo: bool = False) -> DatabaseManager:
    """
    Get or create global database instance.
    
    Args:
        db_url: Database URL (only used on first call)
        echo: Echo SQL statements (only used on first call)
    
    Returns:
        DatabaseManager instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(db_url=db_url, echo=echo)
    return _db_instance
