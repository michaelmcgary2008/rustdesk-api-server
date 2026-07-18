# rustdesk-api-server

## If the project has helped you, giving a star isn't too much, right?

## Please use the latest version 1.2.3 of the client.

[Legacy Chinese README (upstream)](https://github.com/kingmo888/rustdesk-api-server/blob/master/README.md)

<p align="center">
    <i>A Rustdesk API interface implemented in Python, with WebUI management support</i>
    <br/>
    <img src ="https://img.shields.io/badge/Version-1.5.1-blueviolet.svg"/>
    <img src ="https://img.shields.io/badge/Python-3.7|3.8|3.9|3.10|3.11-blue.svg" />
    <img src ="https://img.shields.io/badge/Django-3.2+|4.x-yelow.svg" />
    <br/>
    <img src ="https://img.shields.io/badge/Platform-Windows|Linux-green.svg"/>
    <img src ="https://img.shields.io/badge/Docker-arm|arm64|amd64-blue.svg" />
</p>

![Main Page](images/front_main.png)

## Features

- Supports self-registration and login on the front-end webpage.
  - Registration and login pages:
  ![Front Registration](images/front_reg.png)
  ![Front Login](images/front_login.png)

- Supports displaying device information on the front end, divided into administrator and user versions.
- Supports custom aliases (remarks).
- Supports backend management.
- Supports colored tags.
![Rust Books](images/rust_books.png)

- Supports device online statistics.
- Supports saving device passwords.
- Automatically manages tokens and keeps them alive using the heartbeat interface.
- Supports sharing devices with other users.
![Rust Share](images/share.png)
- Supports web control terminal (currently only supports non-SSL mode, see below for usage issues)
![Rust Share](images/webui.png)

Admin Home Page:
![Admin Main](images/admin_main.png)

## Installation

### Method 1: Out-of-the-box

Only supports Windows: download from Releases and run the bundled launcher (`start.bat` in the release package). Screenshot:

![Windows Run Directly Version](/images/windows_run.png)


### Method 2: Running the Code

```bash
git clone https://github.com/kingmo888/rustdesk-api-server.git
cd rustdesk-api-server
pip install -r requirements.txt
# Port 21114 is the usual RustDesk API port
python manage.py runserver 0.0.0.0:21114
```

Open `http://<host>:<port>` in a browser.

**Note**: On CentOS, Django 4 may fail with the system SQLite. Patch `django/db/backends/sqlite3/base.py` in site-packages to use `pysqlite3` if needed (see Django docs / upstream README).

### Method 3: Docker Run

#### Build locally

```bash
git clone https://github.com/kingmo888/rustdesk-api-server.git
cd rustdesk-api-server
docker compose --compatibility up --build -d
```

#### Pre-built image

```bash
docker run -d \
  --name rustdesk-api-server \
  -p 21114:21114 \
  -e CSRF_TRUSTED_ORIGINS=http://yourdomain.com:21114 \
  -e ID_SERVER=yourdomain.com \
  -v /yourpath/db:/rustdesk-api-server/db \
  -v /etc/timezone:/etc/timezone:ro \
  -v /etc/localtime:/etc/localtime:ro \
  --network bridge \
  --restart unless-stopped \
  ghcr.io/kingmo888/rustdesk-api-server:latest
```

See `docker-compose.yaml` in this repo for a compose example.

### Synology DSM 7 (Container Manager)

Use `docker-compose.synology.yaml` (no `/etc/timezone` mounts; `./db` volume for SQLite).

**Build the image** (on any Mac/PC/Linux with Docker Desktop or Engine):

```bash
cd rustdesk-api-server
docker build -t rustdesk-api-server:local .
```

**AMD64 / x86_64 NAS** (e.g. Synology with **AMD Ryzen Embedded V1500B**, Intel Atom, etc.): build for `linux/amd64` so the image matches the CPU (especially if you build on Apple Silicon):

```bash
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t rustdesk-api-server:amd64 .
docker save rustdesk-api-server:amd64 -o rustdesk-api-server-amd64.tar
```

Import `rustdesk-api-server-amd64.tar` on the NAS (Container Manager → Image → Add from file), then use `image: rustdesk-api-server:amd64` in compose.

**Save and copy to the NAS** (optional; avoids building on the NAS):

```bash
docker save rustdesk-api-server:local -o rustdesk-api-server-local.tar
```

On DSM: **Container Manager → Image → Add → Add from file** → select the `.tar`. Then create a project from a compose file that uses `image: rustdesk-api-server:local` and **remove** the `build:` section from `docker-compose.synology.yaml`.

**Or build on the NAS:** copy the **entire** repository folder to a share (e.g. `docker/rustdesk-api-server/`), edit `CSRF_TRUSTED_ORIGINS` in `docker-compose.synology.yaml`, ensure a `db` subfolder exists next to the compose file, then in Container Manager use **Create → Project** and point it at that folder.

Open `http://<NAS-IP>:21114`. If you use Synology **reverse proxy with HTTPS**, set `CSRF_TRUSTED_ORIGINS` to your public `https://...` URL.

## Environment Variables

| Variable Name | Reference Value | Note |
| ---- | ------- | ----------- |
| `HOST` | Default `0.0.0.0` | Bind address |
| `TZ` | Default `Asia/Shanghai`, optional | Timezone |
| `SECRET_KEY` | Optional | Django secret |
| `CSRF_TRUSTED_ORIGINS` | Optional | e.g. `http://yourdomain.com:21114`; delete variable to disable (do not leave empty) |
| `ID_SERVER` | Optional | ID / relay host for the web client |
| `DEBUG` | Optional, default `False` | Debug mode |
| `ALLOW_REGISTRATION` | Optional, default `True` | Allow new registrations |
| Database | | SQLite is the default; skip MySQL/Postgres vars if unused |
| `DATABASE_TYPE` | `SQLITE`, `MYSQL`, or `POSTGRESQL` | |
| `MYSQL_*` | | See `rustdesk_server_api/settings.py` |
| `POSTGRES_DBNAME` / `POSTGRES_HOST` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT` | | Required when `DATABASE_TYPE=POSTGRESQL`; see `docker-compose.postgres.yaml` |
| `SQLITE_BUSY_TIMEOUT` | Optional, default `30` | Seconds SQLite waits on lock (many clients hitting `/api/heartbeat`) |

See [tutorial/sqlite2mysql.md](tutorial/sqlite2mysql.md) for SQLite → MySQL migration. For PostgreSQL, use [docker-compose.postgres.yaml](docker-compose.postgres.yaml) (bundled `postgres:15-alpine` sidecar); migrate existing SQLite data with `manage.py dumpdata` → `loaddata`.

## Usage notes

- **RustDesk “API server” URL:** use the **origin only** (scheme + host + port), e.g. `https://ab.example.org` or `https://ab.example.org:443`. The open-source client builds URLs as **`{api-server}/api/heartbeat`** (and similarly for other routes)—see `heartbeat_url()` in [rustdesk/src/hbbs_http/sync.rs](https://github.com/rustdesk/rustdesk/blob/master/src/hbbs_http/sync.rs). So the request path becomes **`/api/api/...` only if** the stored **`api-server` value already ends with `/api`** (trailing slash is trimmed, but a path suffix is not). That can be easy to miss if settings came from an old **Import server config**, **custom client**, or **MDM** while the UI you checked looks empty or different.
- **Reverse proxy:** your upstream URL can be “plain” `http://127.0.0.1:21114` with no `/api` in the field and you can still get a bad path if something in front **rewrites** or **prefixes** the path (portal subpath, chained proxies, odd `proxy_pass` + `rewrite` combos). A **404** on `/api/api/heartbeat` means the path was doubled. Fix it at the source (the client's `api-server` value or the proxy rewrite) rather than in the server.
- **SQLite on a busy NAS:** prefer **MySQL** for many simultaneous clients; otherwise raise `SQLITE_BUSY_TIMEOUT` and avoid running extra DB tools against `db.sqlite3` while the container is up.
- First registered user becomes super-admin when the database is empty.
- Clients typically send device info when installed as a service (non-portable install).
- Web control: set `ID_SERVER` or `settings.ID_SERVER`. Non-SSL web UI: use `http://` for WebSocket (not `https://`) unless you terminate TLS correctly.
- Behind nginx + HTTPS: set `CSRF_TRUSTED_ORIGINS` to your public URL (`https://...`).

## Related projects

- [RustDesk-ID-Changer](https://github.com/abdullah-erturk/RustDesk-ID-Changer)
- [rustdesk](https://github.com/rustdesk/rustdesk)
- [rustdesk-server](https://github.com/rustdesk/rustdesk-server)

## Stargazers over time
[![Stargazers over time](https://starchart.cc/kingmo888/rustdesk-api-server.svg?variant=adaptive)](https://starchart.cc/kingmo888/rustdesk-api-server)
