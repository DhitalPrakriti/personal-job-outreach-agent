#!/bin/bash
# ─── Backup Script ─────────────────────────────────────────
# Backs up PostgreSQL to Backblaze B2
# Run via cron: 0 3 * * * /path/to/backup.sh
# ───────────────────────────────────────────────────────────

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/backups"
B2_BUCKET="${B2_BUCKET_NAME:-email-agent-backups}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# PostgreSQL dump
echo "  → Dumping PostgreSQL..."
docker exec postgres pg_dump -U "${POSTGRES_USER:-agent}" "${POSTGRES_DB:-email_agent}" | gzip > "$BACKUP_DIR/pg_${TIMESTAMP}.sql.gz"

# Upload to B2
echo "  → Uploading to Backblaze B2..."
b2 upload-file "$B2_BUCKET" "$BACKUP_DIR/pg_${TIMESTAMP}.sql.gz" "postgres/pg_${TIMESTAMP}.sql.gz"

# Cleanup local
rm -rf "$BACKUP_DIR"

# Remove backups older than 30 days from B2
echo "  → Cleaning old backups..."
b2 ls "$B2_BUCKET" postgres/ | head -n -30 | while read -r file; do
  b2 delete-file-version "$file" 2>/dev/null || true
done

echo "[$(date)] Backup complete ✓"
