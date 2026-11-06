"""System 2.E: Trading Knowledge Base & Retrieval-Augmented Generation (RAG) Engine.
Stores trading books, strategy documentation, and internal rules in SQLite.
Provides local vector / semantic retrieval using TF-IDF and cosine similarity.
"""
from dataclasses import dataclass
import json
import sqlite3
import time
from typing import Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import DB_PATH
import db


def init_kb_table(path: str = DB_PATH) -> None:
    """Initialize knowledge base table in SQLite."""
    with db.get_connection(path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            created_at REAL NOT NULL
        );
        """)


def add_document(title: str, content: str, category: str = "STRATEGY", tags: str = "", path: str = DB_PATH) -> int:
    """Add a document / trading book chapter / rule to the knowledge base."""
    init_kb_table(path)
    with db.get_connection(path) as conn:
        cur = conn.execute(
            "INSERT INTO knowledge_base (title, category, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
            (title, category, content, tags, time.time()),
        )
        return cur.lastrowid or 0


def get_all_documents(path: str = DB_PATH) -> list[dict[str, Any]]:
    """Retrieve all indexed documents."""
    init_kb_table(path)
    with db.get_connection(path) as conn:
        rows = conn.execute("SELECT * FROM knowledge_base ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


def search_knowledge_base(query: str, top_k: int = 3, path: str = DB_PATH) -> list[dict[str, Any]]:
    """Search knowledge base using TF-IDF vector embeddings and cosine similarity."""
    docs = get_all_documents(path)
    if not docs:
        return []

    corpus = [f"{d['title']} {d['tags']} {d['content']}" for d in docs]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)
    query_vec = vectorizer.transform([query])

    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    ranked_indices = similarities.argsort()[::-1][:top_k]

    results = []
    for idx in ranked_indices:
        score = float(similarities[idx])
        if score > 0.05:  # Relevance threshold
            doc = dict(docs[idx])
            doc["similarity_score"] = round(score, 3)
            results.append(doc)

    return results


def seed_default_knowledge_base(path: str = DB_PATH) -> None:
    """Seed foundational trading rules and market structure principles if empty."""
    docs = get_all_documents(path)
    if len(docs) > 0:
        return

    default_rules = [
        {
            "title": "Strict Risk Management Rules",
            "category": "RISK",
            "tags": "risk, lot size, stop loss, capital preservation",
            "content": "Rule 1: Never risk more than 1% of total equity on any single trade. Rule 2: Every single order must have a hard stop loss at inception. Rule 3: Maintain a minimum 1:2 risk to reward ratio. Rule 4: Halt trading if daily loss reaches 3% of account balance.",
        },
        {
            "title": "Fair Value Gap & Market Structure Guidelines",
            "category": "TECHNICAL",
            "tags": "fvg, order block, bos, choch, price action",
            "content": "A Fair Value Gap (FVG) represents an imbalance created by aggressive displacement. Trade in the direction of the higher timeframe Break of Structure (BOS). Enter on retracement into the FVG confluence zone, placing Stop Loss on the opposing side of the order block.",
        },
        {
            "title": "Commodities & Gold (XAUUSD) Trading Characteristics",
            "category": "COMMODITIES",
            "tags": "gold, xauusd, inflation, interest rates, dollar",
            "content": "Gold is heavily driven by real interest rate expectations, US Dollar strength (DXY), and geopolitical risk. High volatility expands during New York session overlap. Avoid trading inside tight ranges prior to FOMC or CPI releases.",
        },
        {
            "title": "Crude Oil (WTI / USOUSD) Volatility Guidelines",
            "category": "COMMODITIES",
            "tags": "oil, crude, usousd, wti, opec, inventory",
            "content": "Crude oil is sensitive to weekly EIA inventory reports and OPEC policy announcements. Respect supply and demand breakout levels. Always use trailing stops to lock in profit after 1.5R moves.",
        },
    ]

    for item in default_rules:
        add_document(item["title"], item["content"], item["category"], item["tags"], path=path)


# Auto-seed on load
seed_default_knowledge_base()

