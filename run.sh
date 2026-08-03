#!/bin/sh

cd /rustdesk-api-server;

# Wait for PostgreSQL before migrating (psycopg2-binary is baked into the image).
if [ "${DATABASE_TYPE}" = "POSTGRESQL" ]; then
    echo "Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 30); do
        python3 -c "
import sys, os
try:
    import psycopg2
    conn = psycopg2.connect(
        dbname=os.environ.get('POSTGRES_DBNAME'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD'),
        host=os.environ.get('POSTGRES_HOST'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        connect_timeout=3,
    )
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'Not ready: {e}')
    sys.exit(1)
" && break
        echo "Attempt $i/30 - waiting 3s..."
        sleep 3
    done
fi

# Only initialize the bundled SQLite backup when using the SQLite backend.
if [ "${DATABASE_TYPE:-SQLITE}" = "SQLITE" ] && [ ! -e "./db/db.sqlite3" ]; then
    cp "./db_bak/db.sqlite3" "./db/db.sqlite3"
    echo "First run: initializing SQLite database from backup"
fi

# Do not run makemigrations in production containers (locks DB, breaks under load).
python manage.py migrate --noinput

if [ "${USE_DEV_SERVER}" = "True" ]; then
    exec python manage.py runserver $HOST:21114
fi

# Gunicorn bounds concurrency: runserver spawned an unbounded thread per
# request, so any DB stall piled up threads until all Postgres connections
# were exhausted. workers*threads caps in-flight requests (and DB connections).
exec gunicorn rustdesk_server_api.wsgi:application \
    --bind "${HOST}:21114" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads "${GUNICORN_THREADS:-8}" \
    --timeout "${GUNICORN_TIMEOUT:-90}" \
    --access-logfile - \
    --error-logfile -
