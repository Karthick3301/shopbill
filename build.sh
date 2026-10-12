#!/usr/bin/env bash
# Render build step: install deps, collect static files, run migrations.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Demo data only when SEED_DEMO_DATA=true is set on Render.
if [ "$SEED_DEMO_DATA" = "true" ]; then
  python manage.py seed_demo_data
fi