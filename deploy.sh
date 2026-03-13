#!/usr/bin/env bash
# Deploy Rhizome to thisminute.org/rhizome
# Static files served by nginx. API proxied to FastAPI via nginx.
#
# Usage:
#   bash deploy.sh           # Deploy frontend only
#   bash deploy.sh --api     # Deploy frontend + API
set -euo pipefail

INSTANCE="thisminute"
ZONE="us-central1-a"
REMOTE_DIR="/opt/rhizome"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_API=false

if [[ "${1:-}" == "--api" ]]; then
    DEPLOY_API=true
fi

echo "=== Deploying Rhizome ==="

# 1. Build data.js from structure files
echo "[1/4] Building data.js..."
python "$SCRIPT_DIR/build.py"

# 2. Upload static files to server
echo "[2/4] Uploading static files..."
gcloud compute scp "$SCRIPT_DIR/index.html" "$SCRIPT_DIR/data.js" "$INSTANCE:$REMOTE_DIR/" --zone="$ZONE"

# 3. Deploy API (if requested)
if $DEPLOY_API; then
    echo "[3/4] Deploying API..."
    gcloud compute scp --recurse "$SCRIPT_DIR/api" "$INSTANCE:$REMOTE_DIR/" --zone="$ZONE"
    gcloud compute ssh "$INSTANCE" --zone="$ZONE" --command="
        cd $REMOTE_DIR &&
        python3 -m venv --system-site-packages $REMOTE_DIR/venv 2>/dev/null || true &&
        $REMOTE_DIR/venv/bin/pip install -r api/requirements.txt -q &&
        $REMOTE_DIR/venv/bin/python api/init_db.py &&
        sudo tee /etc/systemd/system/rhizome-api.service > /dev/null <<'UNIT'
[Unit]
Description=Rhizome Social API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/rhizome
ExecStart=/opt/rhizome/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8100
Restart=always
RestartSec=5
Environment=RHIZOME_DB_PATH=/opt/rhizome/api/rhizome.db

[Install]
WantedBy=multi-user.target
UNIT
        sudo chown -R www-data:www-data $REMOTE_DIR/api/ &&
        sudo chmod 775 $REMOTE_DIR/api/ &&
        sudo systemctl daemon-reload &&
        sudo systemctl enable rhizome-api &&
        sudo systemctl restart rhizome-api &&
        echo 'API service restarted'
    "
else
    echo "[3/4] Skipping API deploy (use --api to include)"
fi

# 4. Verify
echo "[4/4] Verifying..."
sleep 1
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://thisminute.org/rhizome/" 2>/dev/null || echo "failed")
echo ""
if [ "$STATUS" = "200" ]; then
    echo "=== Live at: https://thisminute.org/rhizome ==="
else
    echo "=== Deploy complete (HTTP $STATUS) ==="
    echo "Check: https://thisminute.org/rhizome"
fi

if $DEPLOY_API; then
    API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://thisminute.org/rhizome/api/health" 2>/dev/null || echo "failed")
    if [ "$API_STATUS" = "200" ]; then
        echo "=== API healthy ==="
    else
        echo "=== API check: HTTP $API_STATUS (may need nginx proxy config) ==="
    fi
fi
