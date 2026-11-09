#!/system/bin/busybox ash
. /system/xray/auth.sh
TOK=$(session_token)
[ -n "$TOK" ] && busybox rm -f "$SESS/$TOK"
echo "Set-Cookie: xps=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
echo "Content-Type: text/plain"
echo "Cache-Control: no-store"
echo ""
echo "logged out"
