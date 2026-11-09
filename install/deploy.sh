#!/usr/bin/env bash
# PC-side: copy the repo files + ARM binaries to the router over adb and run install/install.sh there.
#   install/deploy.sh [ROUTER_IP] [BIN_DIR]
# ROUTER_IP defaults to 192.168.8.1 (Huawei stock LAN IP). BIN_DIR (default: bin/) must hold
# the release binaries named exactly `xray` and `udprelay`.
# Works from Linux, macOS and Git Bash on Windows; needs adb on PATH and adbd running on the router.
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash: don't rewrite /data/... into C:/Program Files/Git/data/...

# Git Bash: hand adb.exe a C:/... path, since path rewriting is off
ROOT=$(cd "$(dirname "$0")/.." && { pwd -W 2>/dev/null || pwd; })
IP=${1:-192.168.8.1}
BIN=${2:-$ROOT/bin}
DEV="$IP:5555"

for b in xray udprelay; do
  [ -f "$BIN/$b" ] || { echo "missing $BIN/$b (download it from the GitHub release)"; exit 1; }
done

adb connect "$DEV" >/dev/null

# staging needs room for the binaries (~40 MB); /data is only 10 MB on the B310s, so take the
# first writable mount that fits (Huawei's /online update partition usually does)
NEED_KB=$(( ($(wc -c < "$BIN/xray") + $(wc -c < "$BIN/udprelay")) / 1024 + 1024 ))
STAGE=$(adb -s "$DEV" shell "for d in /online /data/local/tmp /tmp; do [ -d \$d ] && [ \$(busybox df -k \$d | busybox tail -1 | busybox awk '{print \$(NF-2)}') -gt $NEED_KB ] && { echo \$d/v2rayhw; break; }; done" </dev/null | tr -d '\r')
[ -n "$STAGE" ] || { echo "no writable mount on the router with ${NEED_KB} KB free for staging"; exit 1; }
echo "staging in $STAGE"
trap 'adb -s "$DEV" shell "rm -rf $STAGE" </dev/null >/dev/null 2>&1' EXIT
adb -s "$DEV" shell "rm -rf $STAGE; mkdir -p $STAGE/bin $STAGE/data/xray" </dev/null

echo "copying files..."
( cd "$ROOT/router" && find system -type f ) | while read -r f; do
  adb -s "$DEV" shell "mkdir -p $STAGE/$(dirname "$f")" </dev/null
  adb -s "$DEV" push "$ROOT/router/$f" "$STAGE/$f" >/dev/null
done
adb -s "$DEV" push "$ROOT/router/data/xray/xray.conf.example" "$STAGE/data/xray/xray.conf.example" >/dev/null
adb -s "$DEV" push "$ROOT/install/install.sh" "$STAGE/install.sh" >/dev/null
adb -s "$DEV" push "$BIN/xray" "$STAGE/bin/xray"
adb -s "$DEV" push "$BIN/udprelay" "$STAGE/bin/udprelay"

echo "installing..."
# no terminal on any fd: daemons the installer starts would otherwise keep `adb shell` open forever
adb -s "$DEV" shell "busybox sh $STAGE/install.sh $STAGE < /dev/null > $STAGE/install.log 2>&1; cat $STAGE/install.log" </dev/null
