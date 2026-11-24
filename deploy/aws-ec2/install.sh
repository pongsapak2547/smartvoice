#!/usr/bin/env bash
# SmartVoice — single-EC2 pilot installer (Ubuntu 24.04 LTS).
#
# Run as root from the copied repository:
#     sudo bash deploy/aws-ec2/install.sh --domain smartvoice.example.com [--s3-bucket my-private-bucket]
#
# What it does (safe to run again for an update):
#   - installs Python venv support, Thai fonts for the PDF report, Caddy (HTTPS)
#     and the AWS CLI (only when --s3-bucket is given)
#   - copies the code to /opt/smartvoice/app, keeping data/ and .env untouched
#   - creates the `smartvoice` system user and a venv with requirements.txt
#   - on first install only: creates .env with a random SMARTVOICE_BOOTSTRAP_PASSWORD
#     (printed once) — the published admin1234 is never used on the server
#   - installs systemd units for the app and the nightly backup, and the Caddyfile
#
# It never prints or changes API keys. Put them in through the Settings page
# (or edit /opt/smartvoice/app/.env) after the first login.
set -euo pipefail

DOMAIN=""
S3_BUCKET=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) DOMAIN="${2:-}"; shift 2 ;;
        --s3-bucket) S3_BUCKET="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "run as root (sudo)" >&2
    exit 1
fi
if [[ -z "$DOMAIN" ]]; then
    echo "--domain is required (a DNS name that points at this instance)" >&2
    exit 2
fi
if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "invalid domain: $DOMAIN" >&2
    exit 2
fi
if [[ -n "$S3_BUCKET" && ! "$S3_BUCKET" =~ ^[a-z0-9.-]{3,63}$ ]]; then
    echo "invalid S3 bucket name: $S3_BUCKET" >&2
    exit 2
fi

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE=/opt/smartvoice
APP="$BASE/app"
VENV="$BASE/venv"
DEPLOY="$SRC_DIR/deploy/aws-ec2"

if [[ ! -f "$SRC_DIR/Home.py" || ! -f "$SRC_DIR/requirements.txt" ]]; then
    echo "run this from a SmartVoice checkout (Home.py not found in $SRC_DIR)" >&2
    exit 1
fi

for tool in flock systemctl apt-get; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
[[ -d /run/systemd/system ]] || { echo "systemd is required" >&2; exit 1; }
[[ "$SRC_DIR" != "$APP" ]] || { echo "Use a separate source checkout" >&2; exit 1; }
[[ ! -L "$APP" && ! -L "$APP/data" && ! -L "$APP/.env" ]] || { echo "Runtime paths must not be symlinks" >&2; exit 1; }
for path in requirements-api.txt deploy/aws-ec2/smartvoice.service deploy/aws-ec2/smartvoice-backup.service deploy/aws-ec2/smartvoice-backup.timer deploy/aws-ec2/backup.sh deploy/aws-ec2/Caddyfile.template; do
    [[ -f "$SRC_DIR/$path" ]] || { echo "Incomplete release: $path" >&2; exit 1; }
done
exec 9>/run/lock/smartvoice-install.lock
flock -n 9 || { echo "Another install is running" >&2; exit 1; }
install -d -o root -g root -m 0755 "$BASE/releases"
RELEASE="$(mktemp -d "$BASE/releases/release-XXXXXXXX")"
chmod 0755 "$RELEASE"
CANDIDATE="$RELEASE/app"
VENV="$RELEASE/venv"
PREVIOUS="$RELEASE/previous"
CONFIG_ROOT=/etc
ACTIVATING=0
VENV_SAVED=0

stop_services() {
    local unit
    for unit in smartvoice-backup.timer smartvoice-backup.service smartvoice.service; do
        if systemctl cat "$unit" >/dev/null 2>&1; then
            systemctl stop "$unit" || return
        fi
    done
}

copy_code() {
    rsync --chown=root:root -a --delete --include '/.env.example' --exclude '/data/' --exclude '/.env' --exclude '/.env.*' "$1/" "$2/"
}

restore_configuration() {
    local path
    for path in systemd/system/smartvoice.service systemd/system/smartvoice-backup.service systemd/system/smartvoice-backup.timer caddy/Caddyfile smartvoice/backup.env; do
        if [[ -f "$PREVIOUS/config/$path" ]]; then
            cp -p "$PREVIOUS/config/$path" "$CONFIG_ROOT/$path" || return
        elif [[ -f "$PREVIOUS/absent/${path//\//_}" ]]; then
            rm -f "$CONFIG_ROOT/$path" || return
        fi
    done
    systemctl daemon-reload
}

restore_previous() {
    stop_services || return
    copy_code "$PREVIOUS/app" "$APP" || return
    if [[ "$VENV_SAVED" == 1 ]]; then
        [[ ! -L "$BASE/venv" ]] || unlink "$BASE/venv" || return
        mv "$PREVIOUS/venv" "$BASE/venv" || return
    elif [[ -L "$BASE/venv" && "$(readlink "$BASE/venv")" == "$VENV" ]]; then
        unlink "$BASE/venv" || return
    fi
    restore_configuration
}

finish_install() {
    local status=$?
    trap - EXIT
    if [[ "$status" != 0 && "$ACTIVATING" == 1 ]]; then
        if restore_previous; then
            echo "Previous code/configuration restored; services remain stopped. Inspect configuration before restarting." >&2
        else
            echo "Rollback incomplete: keep services stopped and restore from $PREVIOUS." >&2
        fi
    fi
    exit "$status"
}

activate_release() {
    stop_services
    ACTIVATING=1
    copy_code "$CANDIDATE" "$APP"
    if [[ -e "$BASE/venv" || -L "$BASE/venv" ]]; then
        mv "$BASE/venv" "$PREVIOUS/venv"
        VENV_SAVED=1
    fi
    ln -s "$VENV" "$BASE/venv"
    systemctl start smartvoice.service
}

trap finish_install EXIT

validate_environment() {
CHECK_DATABASE="${4:-1}" PYTHONPATH="$2" PYTHON_DOTENV_DISABLED=1 "$1" - "$3" <<'PY'
import os
import sys

from dotenv import dotenv_values
from smartvoice import auth, database_backend

values = dotenv_values(sys.argv[1])
os.environ[auth.BOOTSTRAP_PASSWORD_ENV] = values.get(auth.BOOTSTRAP_PASSWORD_ENV) or ""
if auth.bootstrap_password_error():
    sys.exit("Set a valid SMARTVOICE_BOOTSTRAP_PASSWORD in the server .env before starting services.")
os.environ["DATABASE_URL"] = values.get("DATABASE_URL") or ""
if os.environ["DATABASE_URL"] and os.getenv("CHECK_DATABASE", "1") == "1":
    try:
        database_backend.check_schema()
    except Exception:
        sys.exit("PostgreSQL is not ready. Run python -m scripts.migrate_postgres --apply from the app directory before starting services.")
PY
}

if [[ -f "$APP/.env" && -x "$BASE/venv/bin/python" ]]; then
    validate_environment "$BASE/venv/bin/python" "$SRC_DIR" "$APP/.env" 0
fi

echo "==> packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv rsync curl gnupg \
    debian-keyring debian-archive-keyring apt-transport-https \
    fonts-thai-tlwg fonts-noto-core postgresql-client

for tool in python3 rsync; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite after package installation: $tool" >&2; exit 1; }
done

if ! command -v caddy >/dev/null 2>&1; then
    echo "==> Caddy (official apt repository)"
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q
    apt-get install -y -q caddy
fi

if [[ -n "$S3_BUCKET" ]] && ! command -v aws >/dev/null 2>&1 && [[ ! -x /snap/bin/aws ]]; then
    echo "==> AWS CLI"
    snap install aws-cli --classic
fi

echo "==> user and folders"
id smartvoice >/dev/null 2>&1 || useradd --system --home-dir /var/lib/smartvoice --shell /usr/sbin/nologin smartvoice
install -d -o root -g root -m 0755 "$BASE"
install -d -o smartvoice -g smartvoice -m 0700 /var/lib/smartvoice

echo "==> code -> $APP (data/ and .env are kept)"
install -d -o root -g root -m 0755 "$APP" "$CANDIDATE" "$PREVIOUS/app"
copy_code "$APP" "$PREVIOUS/app"
APP="$CANDIDATE"
# rsync applies the first matching rule, so the .env.example include comes first.
# Excluded paths are also protected from --delete, so data/ and .env survive.
rsync -a --delete --chown=root:root \
    --include '/.env.example' \
    --exclude '/data/' --exclude '/.env' --exclude '/.env.*' --exclude '/.git/' \
    --exclude '/.venv/' --exclude '__pycache__/' --exclude '/.pytest_cache/' \
    "$SRC_DIR/" "$APP/"
chmod 0755 "$APP/deploy/aws-ec2/backup.sh"
APP="$BASE/app"
if [[ ! -d "$APP/data" ]]; then
    install -d -o smartvoice -g smartvoice -m 0700 "$APP/data"
fi

echo "==> Python environment"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -r "$CANDIDATE/requirements.txt"

if [[ ! -f "$APP/.env" ]]; then
    echo "==> first install: creating .env"
    cp "$CANDIDATE/.env.example" "$APP/.env"
    bootstrap="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(18))')"
    printf '\n# First Admin password for this server (change it after the first login).\nSMARTVOICE_BOOTSTRAP_PASSWORD=%s\n' "$bootstrap" >> "$APP/.env"
    FIRST_PASSWORD="$bootstrap"
    chown smartvoice:smartvoice "$APP/.env"
    chmod 0600 "$APP/.env"
fi

ln -s "$APP/.env" "$CANDIDATE/.env"
echo "Prepared release: $RELEASE (not active yet)"
validate_environment "$VENV/bin/python" "$CANDIDATE" "$APP/.env"

sed "s/__DOMAIN__/$DOMAIN/" "$DEPLOY/Caddyfile.template" > "$RELEASE/Caddyfile"
caddy validate --config "$RELEASE/Caddyfile" --adapter caddyfile >/dev/null
for path in systemd/system/smartvoice.service systemd/system/smartvoice-backup.service systemd/system/smartvoice-backup.timer caddy/Caddyfile smartvoice/backup.env; do
    if [[ -f "$CONFIG_ROOT/$path" ]]; then
        install -d "$PREVIOUS/config/$(dirname "$path")"
        cp -p "$CONFIG_ROOT/$path" "$PREVIOUS/config/$path"
    else
        install -d "$PREVIOUS/absent"
        touch "$PREVIOUS/absent/${path//\//_}"
    fi
done
stop_services
ACTIVATING=1
install -d -o root -g root -m 0755 /etc/smartvoice
if [[ -n "$S3_BUCKET" ]]; then
    printf 'S3_BUCKET=%s\nS3_PREFIX=smartvoice\n' "$S3_BUCKET" > /etc/smartvoice/backup.env
    chmod 0644 /etc/smartvoice/backup.env
fi
install -m 0644 "$DEPLOY/smartvoice.service" /etc/systemd/system/smartvoice.service
install -m 0644 "$DEPLOY/smartvoice-backup.service" /etc/systemd/system/smartvoice-backup.service
install -m 0644 "$DEPLOY/smartvoice-backup.timer" /etc/systemd/system/smartvoice-backup.timer
systemctl daemon-reload
activate_release
for attempt in {1..30}; do
    if curl --fail --silent --max-time 2 http://127.0.0.1:8501/_stcore/health >/dev/null; then break; fi
    [[ "$attempt" != 30 ]] || { echo "Application health check failed" >&2; exit 1; }
    sleep 1
done
install -m 0644 "$RELEASE/Caddyfile" /etc/caddy/Caddyfile
systemctl enable caddy
systemctl reload caddy || systemctl restart caddy
systemctl enable --now smartvoice.service
systemctl enable --now smartvoice-backup.timer
ACTIVATING=0
echo "Previous release retained at $PREVIOUS (no database or secrets copied)."

echo
echo "SmartVoice is starting at https://$DOMAIN"
echo "  status:  systemctl status smartvoice    logs: journalctl -u smartvoice -f"
if [[ -n "${FIRST_PASSWORD:-}" ]]; then
    echo
    echo "  First login: username 'admin', password: $FIRST_PASSWORD"
    echo "  It is shown only this once (also stored in $APP/.env, readable by root)."
    echo "  Sign in and change it right away; then set the API keys on the Settings page."
fi
