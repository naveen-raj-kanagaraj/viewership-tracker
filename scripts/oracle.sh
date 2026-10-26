#!/bin/bash
# Look after the tracker on the Oracle server (after deploy_oracle.sh). Run on the Mac from the tracker folder:
#   bash scripts/oracle.sh status      is it running, last lines of the log
#   bash scripts/oracle.sh logs        follow the live log (Ctrl+C to stop watching; the tracker keeps running)
#   bash scripts/oracle.sh restart     restart it
#   bash scripts/oracle.sh probe       check YouTube / Kick / Twitch from the server
#   bash scripts/oracle.sh backup      make a database backup on the server and copy it to this Mac (backups/)
#   bash scripts/oracle.sh ssh         open a terminal on the server
#   bash scripts/oracle.sh run <command for track.py>   e.g.  bash scripts/oracle.sh run scene top
cd "$(dirname "$0")/.."
[ -f .server ] || { echo "No .server file: run scripts/deploy_oracle.sh first."; exit 1; }
. ./.server
SSH="ssh -i $KEY -o ConnectTimeout=15 ubuntu@$IP"
PY="cd ~/viewership-tracker && venv/bin/python track.py"
case "$1" in
  status)  $SSH "systemctl is-active tracker; uptime; journalctl -u tracker -n 25 --no-pager" ;;
  logs)    $SSH "journalctl -u tracker -f -n 50" ;;
  restart) $SSH "sudo systemctl restart tracker && sleep 5 && systemctl is-active tracker" ;;
  probe)   $SSH "$PY scene probe" ;;
  backup)  f=$($SSH "$PY backup" | sed -n 's/^Backup saved: \([^ ]*\).*/\1/p'); mkdir -p backups
           [ -n "$f" ] && rsync -az -e "ssh -i $KEY" "ubuntu@$IP:$f" backups/ && echo "Copied to backups/$(basename "$f")" ;;
  ssh)     $SSH ;;
  run)     shift; $SSH "$PY $*" ;;
  *)       sed -n '2,10p' "$0" ;;
esac
