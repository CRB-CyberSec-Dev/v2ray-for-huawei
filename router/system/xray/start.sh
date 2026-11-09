#!/system/bin/busybox ash
DIR=/system/xray
ST=/data/xray
cd "$DIR" || exit 1
RUNNING=$(busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep)
if [ -n "$RUNNING" ]; then
  echo "already running: $RUNNING"
  exit 0
fi
export GOMEMLIMIT=40MiB
export GOGC=40
export GOMAXPROCS=1
busybox setsid "$DIR/xray" run -c "$ST/config.json" > "$ST/xray.log" 2>&1 < /dev/null &
busybox sleep 1
busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep
