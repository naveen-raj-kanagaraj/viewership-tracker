#!/bin/bash
# Move the tracker from this Mac to an Oracle Cloud server (Ubuntu), so it runs 24/7 with the Mac closed.
# Run on the Mac, from the tracker folder:
#
#   bash scripts/deploy_oracle.sh <server public IP> <private key file you downloaded from Oracle>
#   e.g. bash scripts/deploy_oracle.sh 129.146.10.20 ~/Downloads/ssh-key-2026-10-26.key
#
# What it does: stops the tracker and its tunnel on this Mac (only one copy may run), clones the code from GitHub on
# the server (so its self-update keeps working), copies your .env, database, cookies.txt, your own game covers and
# the Cloudflare tunnel login, installs Python packages, and starts it as a service that restarts on crash and on
# reboot. Re-running it is safe (it updates the server copy). Your files on the Mac are left in place as a backup.
set -e
cd "$(dirname "$0")/.."
IP="$1"; KEY_IN="$2"
if [ -z "$IP" ] || [ -z "$KEY_IN" ]; then
    echo "Use: bash scripts/deploy_oracle.sh <server public IP> <private key file>"; exit 1
fi
[ -f "$KEY_IN" ] || { echo "Can't find the key file: $KEY_IN"; exit 1; }
[ -f .env ] || { echo "No .env here. Run this from the viewership-tracker folder."; exit 1; }
[ -f track.py ] || { echo "Run this from the viewership-tracker folder."; exit 1; }

mkdir -p "$HOME/.ssh"
KEY="$HOME/.ssh/tracker-oracle.key"            # kept here because Downloads gets cleaned up
[ "$(cd "$(dirname "$KEY_IN")" && pwd)/$(basename "$KEY_IN")" = "$KEY" ] || cp "$KEY_IN" "$KEY"
chmod 600 "$KEY"
printf 'IP=%s\nKEY=%s\n' "$IP" "$KEY" > .server
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 ubuntu@$IP"
RSYNC="rsync -az -e \"ssh -i $KEY -o StrictHostKeyChecking=accept-new\""

echo "==> 1/6 Checking the server..."
if ! $SSH 'echo ok' >/dev/null 2>&1; then
    echo "Can't log in to ubuntu@$IP. Check: the instance is Running, you used its *Public* IPv4 address,"
    echo "the key is the one downloaded when you created it, and the image is Ubuntu (user 'ubuntu')."
    echo "Some Wi-Fi networks block SSH: try a phone hotspot."
    exit 1
fi
echo "    $($SSH 'uname -m; . /etc/os-release; echo $PRETTY_NAME; free -m | awk "/Mem/{print \$2\" MB RAM\"}"' | tr '\n' ' ')"

echo "==> 2/6 Stopping the tracker on this Mac..."
pkill -f "python[0-9.]* (-u )?track\.py" 2>/dev/null && sleep 3 && echo "    Stopped." || echo "    Wasn't running."
pkill -f "cloudflared tunnel" 2>/dev/null && echo "    Stopped this Mac's tunnel (the server takes over the link)." || true
if [ -f data/tracker.db ]; then
    sqlite3 data/tracker.db "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null 2>&1 || true   # one clean file to copy
fi

echo "==> 3/6 Installing system packages and the code on the server (a few minutes the first time)..."
$SSH 'bash -s' <<'REMOTE'
set -e
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip git sqlite3 rsync >/dev/null
if [ "$(free -m | awk '/Mem/{print $2}')" -lt 2000 ] && [ ! -f /swapfile ]; then    # small (1 GB) machines need swap
    sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo timedatectl set-timezone Asia/Kolkata 2>/dev/null || true
if [ -d ~/viewership-tracker/.git ]; then
    cd ~/viewership-tracker && git fetch -q origin main && git reset -q --hard origin/main
else
    git clone -q https://github.com/naveen-raj-kanagaraj/viewership-tracker.git ~/viewership-tracker
fi
cd ~/viewership-tracker
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip >/dev/null
venv/bin/pip install -q -r requirements.txt
mkdir -p data
REMOTE

echo "==> 4/6 Copying your .env, database, cookies, covers and tunnel login..."
eval $RSYNC .env "ubuntu@$IP:~/viewership-tracker/.env"
[ -f data/tracker.db ] && eval $RSYNC data/tracker.db "ubuntu@$IP:~/viewership-tracker/data/tracker.db" && echo "    Database: $(du -h data/tracker.db | cut -f1)"
[ -f cookies.txt ] && eval $RSYNC cookies.txt "ubuntu@$IP:~/viewership-tracker/cookies.txt" || true
[ -d static/gameart ] && eval $RSYNC static/gameart/ "ubuntu@$IP:~/viewership-tracker/static/gameart/" || true
[ -d exports/private ] && eval $RSYNC exports/private/ "ubuntu@$IP:~/viewership-tracker/exports/private/" || true
if [ -d "$HOME/.cloudflared" ]; then
    eval $RSYNC "$HOME/.cloudflared/" "ubuntu@$IP:~/.cloudflared/"
    $SSH 'chmod 700 ~/.cloudflared && chmod 600 ~/.cloudflared/*'
    echo "    Tunnel login copied (live.letsgrowesports.com keeps working)."
else
    echo "    No ~/.cloudflared on this Mac: the server will use a temporary trycloudflare.com link (sent on Telegram)."
fi
# On the server, nightly backups go to a folder on the server; a synced Mac folder in BACKUP_DIR wouldn't exist there.
$SSH "cd ~/viewership-tracker && sed -i '/^BACKUP_DIR=/d' .env"

echo "==> 5/6 Starting it as a service (restarts on crash and on reboot)..."
$SSH 'bash -s' <<'REMOTE'
set -e
sudo tee /etc/systemd/system/tracker.service >/dev/null <<UNIT
[Unit]
Description=letsgrowesports live viewership tracker
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/viewership-tracker
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/ubuntu/viewership-tracker/venv/bin/python -u track.py
Restart=always
RestartSec=10
KillMode=control-group

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable -q tracker
sudo systemctl restart tracker
REMOTE
sleep 25

echo "==> 6/6 Checking it works from the server..."
$SSH 'systemctl is-active tracker && cd ~/viewership-tracker && timeout 120 venv/bin/python track.py scene probe' || true
echo
echo "Done. The tracker now runs on the server; you can close the Mac."
echo "  Status / logs / restart:  bash scripts/oracle.sh status | logs | restart"
echo "Don't start track.py on the Mac again while the server runs it (two copies would fight over the link)."
