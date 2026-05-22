#!/usr/bin/env python3
"""
News aggregator for Global Intelligence Dashboard.
Fetches RSS feeds → filters by keywords → outputs JSON for each quadrant.
Runs daily via GitHub Actions at 08:00 CST.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, quote

try:
    import feedparser
except ImportError:
    print("pip3 install feedparser")
    sys.exit(1)

CST = timezone(timedelta(hours=8))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

FEEDS = {
    "medical": [
        # PubMed: obesity + metabolic + China
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/erss.cgi?rss_guid=1Tt0RZ0XN9qF8N3YpK2O3xX5Y1Z",
        # WHO News
        "https://www.who.int/rss-feeds/news-english.xml",
        # PubMed: GLP-1 + weight management
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/erss.cgi?rss_guid=1LmKp2QwR5hV8X4Y3n0D9fA7c1Z",
        # CDC Overweight & Obesity
        "https://tools.cdc.gov/api/v2/resources/media/403372.rss",
    ],
    "ai": [
        "https://www.technologyreview.com/feed/",
        "https://techcrunch.com/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini+OR+NVIDIA",
    ],
    "ipo": [
        # HKEX Main Board New Listings
        "https://www.hkex.com.hk/eng/rss/RSSFeed.xml",
    ],
}

# Keywords for filtering relevant articles (case-insensitive)
MEDICAL_KEYWORDS = [
    "obesity", "obese", "weight loss", "weight management", "bariatric",
    "GLP-1", "semaglutide", "tirzepatide", "metabolic", "diabetes",
    "BMI", "overweight", "减重", "肥胖", "体重", "代谢", "GLP-1",
    "糖尿病", "减肥", "体重管理", "减重门诊", "慢病管理",
]

AI_KEYWORDS = [
    "LLM", "GPT-5", "GPT-4", "Claude", "Gemini", "DeepSeek", "NVIDIA",
    "GPU", "transformer", "open source model", "AI agent", "推理",
    "大模型", "人工智能", "深度学习", "MoE", "SWE-bench",
    "machine learning", "neural network", "reinforcement learning",
    "AI chip", "data center", "算力", "芯片", "agent",
]

IPO_KEYWORDS = [
    "IPO", "listing", "HKEX", "港交所", "递表", "聆讯", "挂牌",
    "定价", "募资", "招股", "上市", "18A", "SPAC",
    "Hong Kong Stock Exchange", "SEHK", "主板",
]


def fetch_feed(url, timeout=15):
    """Fetch and parse a single RSS feed."""
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            print(f"  WARN: {url[:60]}... parse warning: {feed.bozo_exception}")
        return feed
    except Exception as e:
        print(f"  ERROR: {url[:60]}... {e}")
        return None


def extract_articles(feed, keywords, max_per_feed=8):
    """Extract and filter articles from a parsed feed."""
    articles = []
    if not feed or not feed.entries:
        return articles

    for entry in feed.entries[:max_per_feed * 2]:  # fetch more, filter down
        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        link = entry.get("link", "")
        published = entry.get("published", "") or entry.get("updated", "")

        # Check if any keyword matches title or summary
        text = (title + " " + summary).lower()
        matched = [kw for kw in keywords if kw.lower() in text]

        if matched:
            # Parse date
            try:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=CST)
            except (AttributeError, TypeError):
                pub_date = None

            articles.append({
                "title": title.strip(),
                "summary": clean_html(summary)[:200].strip(),
                "link": link,
                "source": feed.feed.get("title", "")[:30],
                "date": pub_date.strftime("%m.%d") if pub_date else "",
                "matched_kw": matched[:5],
                "timestamp": pub_date.isoformat() if pub_date else "",
            })

        if len(articles) >= max_per_feed:
            break

    return articles


def clean_html(text):
    """Remove HTML tags."""
    import re
    return re.sub(r"<[^>]+>", "", text)


def fetch_all(category, max_total=10):
    """Fetch all feeds for a category, merge, deduplicate, sort by date."""
    all_articles = []
    seen = set()

    keywords_map = {
        "medical": MEDICAL_KEYWORDS,
        "ai": AI_KEYWORDS,
        "ipo": IPO_KEYWORDS,
    }
    keywords = keywords_map.get(category, [])

    for url in FEEDS.get(category, []):
        print(f"  Fetching: {url[:80]}...")
        feed = fetch_feed(url)
        if feed:
            articles = extract_articles(feed, keywords)
            for a in articles:
                key = a["title"][:60]
                if key not in seen:
                    seen.add(key)
                    all_articles.append(a)

    # Sort by date descending
    all_articles.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_articles[:max_total]


def generate_csrc_data():
    """Generate CSRC ranking data.
    TODO: Replace with actual scraping from csrc.gov.cn.
    For now, generates a placeholder that should be updated manually.
    """
    today = datetime.now(CST)
    # Check if today is Friday (weekday 4)
    friday = today - timedelta(days=today.weekday() - 4) if today.weekday() >= 4 else today - timedelta(days=today.weekday() + 3)

    return {
        "total_queue": 31,
        "tangji_rank": 18,
        "last_updated": friday.strftime("%Y-%m-%d"),
        "next_update": (friday + timedelta(days=7)).strftime("%Y-%m-%d"),
        "source": "中证监国际部 csrc.gov.cn",
        "note": "每周五更新 · 自动爬取待部署"
    }


def main():
    print(f"=== Dashboard News Fetch === {datetime.now(CST).strftime('%Y-%m-%d %H:%M CST')}")

    for category in ["medical", "ai", "ipo"]:
        print(f"\n[{category}]")
        articles = fetch_all(category)
        output_path = os.path.join(DATA_DIR, f"{category}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated": datetime.now(CST).isoformat(),
                "count": len(articles),
                "articles": articles,
            }, f, ensure_ascii=False, indent=2)
        print(f"  Saved {len(articles)} articles → {output_path}")

    # CSRC ranking
    csrc = generate_csrc_data()
    with open(os.path.join(DATA_DIR, "csrc.json"), "w", encoding="utf-8") as f:
        json.dump(csrc, f, ensure_ascii=False, indent=2)
    print(f"\n[csrc] 中证监排名: 第{csrc['tangji_rank']}位 / {csrc['total_queue']}家")


if __name__ == "__main__":
    main()
