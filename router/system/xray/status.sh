#!/system/bin/busybox ash
ST=/data/xray
XRAY_PID=$(busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep | busybox awk '{print $1}' | busybox head -1)
HTTPD_PID=$(busybox ps | busybox grep 'httpd -f -p 0.0.0.0:8081' | busybox grep -v grep | busybox awk '{print $1}' | busybox head -1)
REDIRECT_ACTIVE=no
iptables -t nat -L XRAY_REDIRECT -n >/dev/null 2>&1 && REDIRECT_ACTIVE=yes

if [ -n "$XRAY_PID" ]; then echo "xray: running (pid $XRAY_PID)"; else echo "xray: stopped"; fi
if [ -n "$HTTPD_PID" ]; then echo "panel: running (pid $HTTPD_PID)"; else echo "panel: stopped"; fi
echo "lan_redirect: $REDIRECT_ACTIVE"
echo "---config---"
[ -f "$ST/xray.conf" ] && busybox cat "$ST/xray.conf" | busybox grep -v '^SECRET='
echo "---last_20_log_lines---"
[ -f "$ST/xray.log" ] && busybox tail -n 20 "$ST/xray.log"
