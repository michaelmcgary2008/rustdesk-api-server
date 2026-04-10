# Migrating from the default SQLite database to MySQL

This guide applies to both source installs and Docker.

### 1. Source install (skip if you already run from source)

```bash
git clone https://github.com/kingmo888/rustdesk-api-server.git
cd rustdesk-api-server
pip install -r requirements.txt
```

### 2. Replace the database file

On a fresh install the app uses the default DB. Copy your live `db.sqlite3` to `/db/db.sqlite3` in the project.

### 3. Export data from SQLite

From the project root:

```bash
python manage.py dumpdata > data.json
```

### 4. Configure MySQL

Example empty MySQL database:

| Setting | Value |
| ------- | ----- |
| Host | 192.168.1.33 |
| Database | rustdesk_api |
| User | myuser |
| Password | 123456 |
| Port | 3099 |

In `rustdesk_server_api/settings.py` set:

- `DATABASE_TYPE` → `'MYSQL'`
- `MYSQL_HOST` → e.g. `'192.168.1.33'`
- `MYSQL_DBNAME` → `'rustdesk_api'`
- `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_PORT` as needed

### 5. Create tables in MySQL

```bash
python manage.py makemigrations
python manage.py migrate
```

If `django_content_type` and `auth_permission` already contain rows, truncate them before import (otherwise you may get duplicate key errors).

### 6. Load the dump

```bash
python manage.py loaddata data.json
```

If you get encoding errors, save `data.json` as UTF-8 and retry. Fix any invalid rows in the JSON and re-export from SQLite if needed.

### 7. Docker

If MySQL is already configured, set the MySQL-related environment variables and restart.

If MySQL is new, create the database, import a dump if needed, set env vars, and restart the container.
