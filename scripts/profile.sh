#!/bin/bash
# Read-only: where the tracker spends its time for 20 seconds (py-spy), as % of samples per tracker function.
# Usage: bash scripts/profile.sh
cd "$(dirname "$0")/.." || exit 1
P=$(systemctl show -p MainPID --value tracker)
sudo venv/bin/py-spy record --pid "$P" --duration 20 --rate 50 --format raw --output /tmp/tracker_prof.txt --nonblocking >/dev/null 2>&1
sudo chmod 644 /tmp/tracker_prof.txt
python3 - <<'PY'
import collections
c, own, tot = collections.Counter(), collections.Counter(), 0
for line in open("/tmp/tracker_prof.txt"):
    st, _, n = line.rstrip().rpartition(" ")
    try:
        n = int(n)
    except ValueError:
        continue
    tot += n
    fr = [f for f in st.split(";") if "tracker/" in f or "track.py" in f]
    for f in set(fr):
        c[f] += n
    if "idle" not in st and st:
        own[st.split(";")[-1]] += n
print(f"{tot} samples. Busiest tracker functions (share of all samples, including what they call):")
for f, n in c.most_common(20):
    print(f"  {100 * n / tot:5.1f}%  {f[:140]}")
print("Busiest leaf functions:")
for f, n in own.most_common(10):
    print(f"  {100 * n / tot:5.1f}%  {f[:140]}")
PY
