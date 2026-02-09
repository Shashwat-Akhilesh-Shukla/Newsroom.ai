"""
Data processing utilities for AI Newsroom.

This module provides utilities for:
- Text cleaning and normalization
- Citation extraction and formatting
- Content deduplication
- Text analysis
"""

import re
from typing import List, Dict, Optional
from datetime import datetime
import hashlib


def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    
    Args:
        text: Raw text
        
    Returns:
        Cleaned text
    """
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    
    return text


def extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text.
    
    Args:
        text: Text containing URLs
        
    Returns:
        List of URLs
    """
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)


def format_citation(
    author: str,
    title: str,
    source: str,
    url: str,
    date: Optional[str] = None
) -> str:
    """
    Format a citation in a consistent style.
    
    Args:
        author: Author name
        title: Article/paper title
        source: Source (journal, website, etc.)
        url: URL
        date: Publication date (optional)
        
    Returns:
        Formatted citation
    """
    citation_parts = []
    
    if author:
        citation_parts.append(f"{author}.")
    
    if title:
        citation_parts.append(f'"{title}."')
    
    if source:
        citation_parts.append(f"{source}.")
    
    if date:
        citation_parts.append(f"({date}).")
    
    citation = " ".join(citation_parts)
    
    if url:
        citation += f" Available at: {url}"
    
    return citation


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract keywords from text (simple implementation).
    
    Args:
        text: Text to analyze
        max_keywords: Maximum number of keywords
        
    Returns:
        List of keywords
    """
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    # Extract words
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    
    # Filter stop words and count frequency
    word_freq = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:max_keywords]]


def calculate_content_hash(text: str) -> str:
    """
    Calculate a hash of content for deduplication.
    
    Args:
        text: Content to hash
        
    Returns:
        SHA256 hash
    """
    # Normalize text before hashing
    normalized = clean_text(text.lower())
    return hashlib.sha256(normalized.encode()).hexdigest()


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def count_words(text: str) -> int:
    """
    Count words in text.
    
    Args:
        text: Text to count
        
    Returns:
        Word count
    """
    return len(re.findall(r'\b\w+\b', text))


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time in minutes.
    
    Args:
        text: Text to analyze
        words_per_minute: Average reading speed
        
    Returns:
        Estimated reading time in minutes
    """
    word_count = count_words(text)
    return max(1, round(word_count / words_per_minute))


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    
    Args:
        text: Text to split
        
    Returns:
        List of sentences
    """
    # Simple sentence splitting (can be improved with NLP libraries)
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]


def create_summary_metadata(text: str) -> Dict[str, any]:
    """
    Create metadata summary for text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary with metadata
    """
    return {
        "word_count": count_words(text),
        "character_count": len(text),
        "sentence_count": len(split_into_sentences(text)),
        "reading_time_minutes": estimate_reading_time(text),
        "keywords": extract_keywords(text),
        "content_hash": calculate_content_hash(text),
        "analyzed_at": datetime.utcnow().isoformat()
    }
