#!/usr/bin/env bash
# Daily SmartVoice backup — run by smartvoice-backup.timer as the smartvoice user.
#
# 1. Consistent, integrity-checked SQLite snapshot into data/backups/
#    (scripts/backup_db.py; keeps the newest 14 locally).
# 2. If S3_BUCKET is set in /etc/smartvoice/backup.env, copy snapshots, audio
#    (+ speech-API checkpoints) and warranty proofs to that private bucket with
#    server-side encryption. `sync` without --delete: removing a file locally
#    never removes its copy in S3.
#
# Everything here is customer data. The bucket must block public access.
set -euo pipefail

# The aws CLI is installed as a snap; systemd units may not have /snap/bin on PATH.
export PATH="$PATH:/snap/bin"

APP_DIR=/opt/smartvoice/app
PYTHON=/opt/smartvoice/venv/bin/python
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-smartvoice}"

cd "$APP_DIR"
snapshot="$("$PYTHON" scripts/backup_db.py --out data/backups --keep 14)"
echo "snapshot: $snapshot"

if [[ -z "$S3_BUCKET" ]]; then
    echo "S3_BUCKET not set — local snapshot only"
    exit 0
fi

if ! command -v aws >/dev/null 2>&1; then
    echo "aws CLI not found — cannot upload to s3://$S3_BUCKET" >&2
    exit 1
fi

dest="s3://$S3_BUCKET/$S3_PREFIX"
aws s3 sync data/backups "$dest/backups" --sse AES256 --only-show-errors
for folder in raw_audio warranty_proofs; do
    if [[ -d "data/$folder" ]]; then
        aws s3 sync "data/$folder" "$dest/$folder" --sse AES256 --only-show-errors \
            --exclude "*.tmp"
    fi
done
echo "uploaded to $dest"
