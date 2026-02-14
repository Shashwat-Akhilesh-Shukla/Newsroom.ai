"""
Database layer for persistent storage.

Implements SQLAlchemy models and database operations for the AI Newsroom.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import StaticPool

# Support both SQLAlchemy 1.x and 2.x
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


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
    Manages database connections and operations.
    
    Supports SQLite (default) with optional PostgreSQL support.
    """
    
    def __init__(self, db_url: Optional[str] = None, echo: bool = False):
        """
        Initialize database manager.
        
        Args:
            db_url: Database URL (defaults to SQLite: newsroom.db)
            echo: Whether to echo SQL statements (for debugging)
        """
        if db_url is None:
            # Default to SQLite in project root
            db_path = Path("newsroom.db")
            db_url = f"sqlite:///{db_path}"
            logger.info(f"Using SQLite database: {db_path}")
        
        # Create engine
        if db_url.startswith("sqlite"):
            # SQLite-specific settings
            self.engine = create_engine(
                db_url,
                echo=echo,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        else:
            # PostgreSQL or other databases
            self.engine = create_engine(db_url, echo=echo, pool_pre_ping=True)
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        
        # Create tables
        self._create_tables()
        
        logger.info("Database initialized successfully")
    
    def _create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        logger.debug("Database tables created/verified")
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Get a database session (context manager).
        
        Usage:
            with db.get_session() as session:
                topic = session.query(Topic).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    # CRUD Operations for Topic
    
    def create_topic(self, title: str, confidence: float, meta_data: Optional[Dict] = None) -> Topic:
        """Create a new topic."""
        with self.get_session() as session:
            topic = Topic(
                title=title,
                confidence=confidence,
                meta_data=meta_data or {}
            )
            session.add(topic)
            session.flush()
            session.refresh(topic)
            logger.info(f"Created topic: {topic}")
            return topic
    
    def get_topic(self, topic_id: int) -> Optional[Topic]:
        """Get topic by ID."""
        with self.get_session() as session:
            return session.query(Topic).filter(Topic.topic_id == topic_id).first()
    
    def update_topic_status(self, topic_id: int, status: str) -> bool:
        """Update topic status."""
        with self.get_session() as session:
            topic = session.query(Topic).filter(Topic.topic_id == topic_id).first()
            if topic:
                topic.status = status
                topic.updated_at = datetime.utcnow()
                logger.info(f"Updated topic {topic_id} status to: {status}")
                return True
            return False
    
    def get_topics_by_status(self, status: str) -> List[Topic]:
        """Get all topics with a specific status."""
        with self.get_session() as session:
            return session.query(Topic).filter(Topic.status == status).all()
    
    # CRUD Operations for Research
    
    def create_research(self, topic_id: int, source: str, content: str, 
                       citations: Optional[List[Dict]] = None, meta_data: Optional[Dict] = None) -> Research:
        """Create research note."""
        with self.get_session() as session:
            research = Research(
                topic_id=topic_id,
                source=source,
                content=content,
                citations=citations or [],
                meta_data=meta_data or {}
            )
            session.add(research)
            session.flush()
            session.refresh(research)
            logger.info(f"Created research note: {research}")
            return research
    
    def get_research_by_topic(self, topic_id: int) -> List[Research]:
        """Get all research notes for a topic."""
        with self.get_session() as session:
            return session.query(Research).filter(Research.topic_id == topic_id).all()
    
    # CRUD Operations for Draft
    
    def create_draft(self, topic_id: int, content: str, version: int = 1,
                    meta_data: Optional[Dict] = None) -> Draft:
        """Create a new draft."""
        word_count = len(content.split())
        with self.get_session() as session:
            draft = Draft(
                topic_id=topic_id,
                version=version,
                content=content,
                word_count=word_count,
                meta_data=meta_data or {}
            )
            session.add(draft)
            session.flush()
            session.refresh(draft)
            logger.info(f"Created draft: {draft}")
            return draft
    
    def get_latest_draft(self, topic_id: int) -> Optional[Draft]:
        """Get the latest draft version for a topic."""
        with self.get_session() as session:
            return session.query(Draft)\
                .filter(Draft.topic_id == topic_id)\
                .order_by(Draft.version.desc())\
                .first()
    
    def get_drafts_by_topic(self, topic_id: int) -> List[Draft]:
        """Get all drafts for a topic."""
        with self.get_session() as session:
            return session.query(Draft)\
                .filter(Draft.topic_id == topic_id)\
                .order_by(Draft.version)\
                .all()
    
    # CRUD Operations for Feedback
    
    def create_feedback(self, agent: str, target_agent: str, content: str,
                       decision: Optional[str] = None, meta_data: Optional[Dict] = None) -> Feedback:
        """Create feedback entry."""
        with self.get_session() as session:
            feedback = Feedback(
                agent=agent,
                target_agent=target_agent,
                content=content,
                decision=decision,
                meta_data=meta_data or {}
            )
            session.add(feedback)
            session.flush()
            session.refresh(feedback)
            logger.info(f"Created feedback: {feedback}")
            return feedback
    
    def get_feedback_by_agent(self, agent: str) -> List[Feedback]:
        """Get all feedback from a specific agent."""
        with self.get_session() as session:
            return session.query(Feedback).filter(Feedback.agent == agent).all()
    
    # CRUD Operations for Publication
    
    def create_publication(self, topic_id: int, draft_id: Optional[int] = None,
                          platform: str = 'local', url: Optional[str] = None,
                          meta_data: Optional[Dict] = None) -> Publication:
        """Create publication record."""
        with self.get_session() as session:
            publication = Publication(
                topic_id=topic_id,
                draft_id=draft_id,
                platform=platform,
                url=url,
                meta_data=meta_data or {}
            )
            session.add(publication)
            session.flush()
            session.refresh(publication)
            logger.info(f"Created publication: {publication}")
            return publication
    
    def get_publications(self, platform: Optional[str] = None) -> List[Publication]:
        """Get all publications, optionally filtered by platform."""
        with self.get_session() as session:
            query = session.query(Publication)
            if platform:
                query = query.filter(Publication.platform == platform)
            return query.all()
    
    # Utility Methods
    
    def get_workflow_history(self, topic_id: int) -> Dict[str, Any]:
        """
        Get complete workflow history for a topic.
        
        Returns:
            Dictionary with topic, research, drafts, feedback, and publications
        """
        with self.get_session() as session:
            topic = session.query(Topic).filter(Topic.topic_id == topic_id).first()
            if not topic:
                return {}
            
            return {
                'topic': topic,
                'research': session.query(Research).filter(Research.topic_id == topic_id).all(),
                'drafts': session.query(Draft).filter(Draft.topic_id == topic_id).order_by(Draft.version).all(),
                'feedback': session.query(Feedback).all(),  # All feedback for context
                'publications': session.query(Publication).filter(Publication.topic_id == topic_id).all()
            }
    
    def cleanup_old_data(self, days: int = 30):
        """Delete data older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            # Delete old topics and cascade will handle related records
            deleted = session.query(Topic)\
                .filter(Topic.created_at < cutoff_date)\
                .filter(Topic.status != 'published')\
                .delete()
            logger.info(f"Cleaned up {deleted} old topics")


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
