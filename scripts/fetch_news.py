#!/usr/bin/env python3
"""
News aggregator — fetches RSS feeds and MERGES new articles with existing seed data.
Seed data is preserved; new RSS articles are added to the top.
Runs daily via GitHub Actions at 08:00 CST.
"""
import json, os, re, sys, urllib.parse
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

try:
    import feedparser
except ImportError:
    print("pip3 install feedparser")
    sys.exit(1)

FEEDS = {
    "medical": [
        "https://www.who.int/rss-feeds/news-english.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
    ],
    "ai": [
        "https://www.technologyreview.com/feed/",
        "https://techcrunch.com/feed/",
        "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini+OR+NVIDIA",
    ],
    "ipo": [],
}

KEYWORDS = {
    "medical": ["obesity","weight","GLP-1","semaglutide","tirzepatide","metabolic","diabetes","BMI","overweight","bariatric","减重","肥胖","体重","代谢","糖尿病"],
    "ai": ["LLM","GPT","Claude","Gemini","DeepSeek","NVIDIA","GPU","transformer","AI agent","推理","大模型","人工智能","MoE","SWE-bench","算力","芯片","agent","OpenAI","Anthropic"],
    "ipo": ["IPO","listing","HKEX","港交所","递表","聆讯","挂牌","定价","募资","招股","18A"],
}

def clean(s):
    return re.sub(r'<[^>]+>', '', s)[:300]

def fetch_new(category, max_new=5):
    """Fetch new articles from RSS, returning only genuinely new items."""
    articles = []
    seen = set()
    for url in FEEDS.get(category, []):
        try:
            f = feedparser.parse(url)
            for e in f.entries[:10]:
                title = e.get('title','').strip()
                link = e.get('link','')
                summary = clean(e.get('summary','') or e.get('description',''))
                text = (title + ' ' + summary).lower()
                if any(kw.lower() in text for kw in KEYWORDS.get(category,[])):
                    key = title[:60]
                    if key not in seen:
                        seen.add(key)
                        pub = ''
                        if hasattr(e, 'published_parsed') and e.published_parsed:
                            pub = f"{e.published_parsed.tm_mon:02d}.{e.published_parsed.tm_mday:02d}"
                        articles.append({
                            'title': title, 'link': link,
                            'source': f.feed.get('title','')[:25] if hasattr(f.feed,'get') else 'RSS',
                            'date': pub, 'tags': [], 'badge': 'NEW', 'badge_type': 'chip-3'
                        })
        except Exception as ex:
            print(f"  RSS error {url[:50]}: {ex}")
    return articles[:max_new]


def main():
    print(f"=== News Refresh {datetime.now(CST).strftime('%Y-%m-%d %H:%M CST')} ===")

    csrc = {
        'tangji_rank': 190, 'total': 734,
        'updated': datetime.now(CST).strftime('%Y-%m-%d'),
        'source': '中证监国际部', 'note': '每周五更新 · 需手动确认排名'
    }
    with open(os.path.join(DATA_DIR, 'csrc.json'), 'w') as f:
        json.dump(csrc, f, ensure_ascii=False, indent=2)

    for cat in ['medical', 'ai', 'ipo']:
        path = os.path.join(DATA_DIR, f'{cat}.json')
        # Load existing data
        try:
            with open(path) as f:
                existing = json.load(f)
        except:
            existing = {'articles': [], 'metrics': {}}

        old_articles = existing.get('articles', [])
        new_articles = fetch_new(cat, max_new=5)

        # Merge: put new on top, deduplicate by title prefix
        old_titles = {a['title'][:60] for a in old_articles}
        truly_new = [a for a in new_articles if a['title'][:60] not in old_titles]

        merged = truly_new + old_articles
        # Trim to max 10 articles
        merged = merged[:10]

        existing['articles'] = merged
        existing['updated'] = datetime.now(CST).isoformat()
        existing['source'] = 'rss_merged'

        with open(path, 'w') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        print(f"  {cat}: +{len(truly_new)} new, total {len(merged)} articles")

    # Update ipo csrc
    with open(os.path.join(DATA_DIR, 'ipo.json')) as f:
        ipo = json.load(f)
    ipo['csrc'] = csrc
    with open(os.path.join(DATA_DIR, 'ipo.json'), 'w') as f:
        json.dump(ipo, f, ensure_ascii=False, indent=2)

    print("Done!")

if __name__ == "__main__":
    main()
