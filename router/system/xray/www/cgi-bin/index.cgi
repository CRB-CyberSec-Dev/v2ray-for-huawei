#!/system/bin/busybox ash
# busybox httpd runs this for "/" because www/ has no index.html: panel when logged in, login page otherwise
. /system/xray/auth.sh
echo "Content-Type: text/html; charset=utf-8"
echo "Cache-Control: no-store"
echo "X-Frame-Options: DENY"
echo ""
if auth_ok; then
  busybox cat /system/xray/panel.html
else
  busybox cat /system/xray/login.html
fi
