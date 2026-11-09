#!/system/bin/busybox ash
PIDS=$(busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep | busybox awk '{print $1}')
if [ -z "$PIDS" ]; then
  echo "not running"
  exit 0
fi
for p in $PIDS; do
  busybox kill "$p" 2>/dev/null
done
busybox sleep 1
PIDS2=$(busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep | busybox awk '{print $1}')
for p in $PIDS2; do
  busybox kill -9 "$p" 2>/dev/null
done
echo "stopped"
