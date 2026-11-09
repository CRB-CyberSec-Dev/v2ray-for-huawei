#!/system/bin/busybox ash
. /system/xray/auth.sh
require_auth
DIR=/system/xray
ST=/data/xray
[ -f "$ST/xray.conf" ] && . "$ST/xray.conf"
j() { busybox echo "$1" | busybox tr -d '\\"'; }
rd() { [ -f "$ST/$1" ] && busybox cat "$ST/$1" || busybox echo "$2"; }

XPID=$(busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep | busybox awk '{print $1}' | busybox head -1)
RUN=false; UP=0; RSS=0
if [ -n "$XPID" ]; then
  RUN=true
  NOW=$(busybox date +%s)
  ST=$(busybox stat -c %Y /proc/$XPID 2>/dev/null)
  [ -n "$ST" ] && UP=$((NOW-ST))
  RSS=$(busybox awk '/VmRSS/{print $2}' /proc/$XPID/status 2>/dev/null)
  [ -z "$RSS" ] && RSS=0
fi
RED=false
iptables -t nat -L XRAY_REDIRECT -n >/dev/null 2>&1 && RED=true
UDPB=false
iptables -t filter -L XRAY_UDPBLOCK -n >/dev/null 2>&1 && UDPB=true
UDPT=false
iptables -t nat -L XRAY_UDPREDIR -n >/dev/null 2>&1 && UDPT=true
LOAD=$(busybox awk '{print $1}' /proc/loadavg)
MEMT=$(busybox awk '/^MemTotal/{print $2}' /proc/meminfo)
MEMF=$(busybox awk '/^MemFree/{f=$2} /^Cached/{c=$2} END{print f+c}' /proc/meminfo)
HASSEC=false
[ -n "$SECRET" ] && HASSEC=true
TS=$(rd tunnel_state 1)
UM=$(rd udp_mode direct)
CM=$(rd cipher_mode fast)

echo "Content-Type: application/json"
echo "Cache-Control: no-store"
echo ""
busybox echo "{\"running\":$RUN,\"pid\":\"$XPID\",\"uptime\":$UP,\"rss_kb\":$RSS,\"redirect\":$RED,\"udp_blocked\":$UDPB,\"udp_tunneled\":$UDPT,\"udp_mode\":\"$(j "$UM")\",\"cipher\":\"$(j "$CM")\",\"tunnel_wanted\":\"$(j "$TS")\",\"load\":\"$LOAD\",\"mem_total_kb\":${MEMT:-0},\"mem_avail_kb\":${MEMF:-0},\"config\":{\"proto\":\"$(j "$PROTO")\",\"addr\":\"$(j "$ADDR")\",\"port\":\"$(j "$PORT")\",\"network\":\"$(j "$NETWORK")\",\"security\":\"$(j "$SECURITY")\",\"sni\":\"$(j "$SNI")\",\"fp\":\"$(j "$FP")\",\"wspath\":\"$(j "$WSPATH")\",\"wshost\":\"$(j "$WSHOST")\",\"ssmethod\":\"$(j "$SSMETHOD")\",\"pin\":\"$(j "$PIN")\",\"has_secret\":$HASSEC}}"
