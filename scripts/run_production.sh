#!/bin/bash
# Production environment startup shell script
export FLASK_ENV=production
export FLASK_DEBUG=false

echo "Validating database schema and seeding values..."
python scripts/init_db.py

echo "Starting Gunicorn server on bind 0.0.0.0:8000..."
gunicorn -c gunicorn.conf.py wsgi:app
