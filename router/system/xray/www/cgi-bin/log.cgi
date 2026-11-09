#!/system/bin/busybox ash
. /system/xray/auth.sh
require_auth
echo "Content-Type: text/plain"
echo "Cache-Control: no-store"
echo ""
[ -f /data/xray/xray.log ] && busybox tail -n 40 /data/xray/xray.log
echo "--- watchdog ---"
[ -f /data/xray/watchdog.log ] && busybox tail -n 8 /data/xray/watchdog.log
