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
| Database | | If not using MySQL, skip MySQL vars |
| `DATABASE_TYPE` | `SQLITE` or `MYSQL` | |
| `MYSQL_*` | | See `rustdesk_server_api/settings.py` |

See [tutorial/sqlite2mysql.md](tutorial/sqlite2mysql.md) for SQLite → MySQL migration.

## Usage notes

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
