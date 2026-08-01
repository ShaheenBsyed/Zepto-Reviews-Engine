"""
src.ingestion — source connectors for data collection (Phase 1).

Connectors:
  - play_store_connector.py   : Google Play Store scraper
  - app_store_connector.py    : Apple App Store scraper
  - forum_connector.py        : BeautifulSoup-based forum scraper
  - twitter_connector.py      : Twitter/X API connector (optional)
  - quora_connector.py        : Quora discussions scraper
  - csv_connector.py          : CSV upload connector for surveys/interviews
  - blog_connector.py         : Public blog scraper
  - product_review_connector.py : Product review website scraper
  - ingest_pipeline.py        : Main ingestion orchestration pipeline
  - db.py                     : SQLite raw store read/write
"""