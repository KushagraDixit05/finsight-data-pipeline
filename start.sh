#!/bin/bash
set -e

echo "=== FinSight Data Pipeline Startup ==="

# 1. Verify Docker is available
if ! command -v docker &> /dev/null; then
    echo "[!] Docker could not be found. Please install Docker."
    exit 1
fi

# 2. Start the existing PostgreSQL/pgvector Docker container (finsight-db)
if [ "$(docker ps -a -q -f name=finsight-db)" ]; then
    if [ ! "$(docker ps -q -f name=finsight-db)" ]; then
        echo "Starting existing finsight-db container..."
        docker start finsight-db > /dev/null
    fi
else
    echo "[!] finsight-db container does not exist. Please create it first according to project instructions."
    exit 1
fi

# 3. Wait until PostgreSQL is ready
echo "Waiting for PostgreSQL to be ready..."
until docker exec finsight-db pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
done

# 4. Verify .env file exists without printing its secrets
if [ ! -f .env ]; then
    echo "[!] .env file not found. Please create one based on .env.example"
    exit 1
fi

# 5. Activate the existing .venv
if [ ! -d .venv ]; then
    echo "[!] .venv not found. Please run python -m venv .venv and install dependencies."
    exit 1
fi
source .venv/bin/activate

# 6. Ensure project dependencies are available
pip install -e ".[dev]" > /dev/null 2>&1

# 7. Run database migrations safely
echo "Running database migrations..."
alembic upgrade head > /dev/null 2>&1

# 8. Run ingestion with/without debug flag
DEBUG_FLAG=""
if [ "$1" == "--debug" ]; then
    DEBUG_FLAG="--debug"
fi

echo "Starting data pipeline ingestion..."
python -m src.news.scheduler.run_ingestion $DEBUG_FLAG

# 9. Clean database summary
echo ""
echo "=== Database Summary ==="
python -c "
from src.news.database.session import SessionLocal
from src.news.database.models import NewsArticle
from sqlalchemy import func, desc

db = SessionLocal()
try:
    total = db.query(NewsArticle).count()
    print(f'Total articles stored: {total}')
    
    print('\nArticles by source:')
    sources = db.query(NewsArticle.source, func.count(NewsArticle.id)).group_by(NewsArticle.source).all()
    for source, count in sources:
        source_val = source.value if hasattr(source, 'value') else source
        print(f'  - {source_val}: {count}')
        
    print('\nLatest 5 articles:')
    latest = db.query(NewsArticle).order_by(desc(NewsArticle.published_at)).limit(5).all()
    if not latest:
        print('  - (No articles found)')
    for art in latest:
        source_val = art.source.value if hasattr(art.source, 'value') else art.source
        print(f'  - [{source_val}] {art.title} ({art.published_at})')
except Exception as e:
    print(f'[!] Could not fetch database summary: {e}')
finally:
    db.close()
"
echo "========================"
