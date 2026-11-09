#!/system/bin/busybox ash
. /system/xray/auth.sh
require_auth
echo "Content-Type: application/json"
echo "Cache-Control: no-store"
echo ""
B=busybox
set -- $($B awk '/^cpu /{t=0;for(i=2;i<=NF;i++)t+=$i;print t, $5+$6}' /proc/stat)
CT=$1; CI=$2
ticks() { [ -n "$1" ] && $B awk '{print $14+$15}' /proc/$1/stat 2>/dev/null || echo 0; }
rss() { [ -n "$1" ] && $B awk '/VmRSS/{print $2}' /proc/$1/status 2>/dev/null || echo 0; }
XP=$($B ps | $B grep '/system/xray/xray run' | $B grep -v grep | $B awk '{print $1}' | $B head -1)
RP=$($B ps | $B grep '/system/xray/udprelay' | $B grep -v grep | $B awk '{print $1}' | $B head -1)
XT=$(ticks "$XP"); XR=$(rss "$XP"); RT=$(ticks "$RP"); RR=$(rss "$RP")
set -- $($B awk '/^MemTotal/{t=$2}/^MemFree/{f=$2}/^Buffers/{b=$2}/^Cached/{c=$2}END{print t,f,b,c}' /proc/meminfo)
MT=$1; MF=$2; MB=$3; MC=$4
net() { $B sed 's/:/ /' /proc/net/dev | $B awk -v i="$1" '$1==i{print $2, $10}'; }
set -- $(net wan0); WR=${1:-0}; WT=${2:-0}
set -- $(net br0); LR=${1:-0}; LT=${2:-0}
set -- $($B cat /proc/loadavg); L1=$1; L5=$2; L15=$3
CC=$($B cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null || echo 0)
CM=$($B cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || echo 0)
TEMP=$($B cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)
UPS=$($B awk '{print int($1)}' /proc/uptime)
NOW=$($B date +%s)
$B echo "{\"t\":$NOW,\"cpu_total\":$CT,\"cpu_idle\":$CI,\"xray_ticks\":${XT:-0},\"xray_rss\":${XR:-0},\"relay_ticks\":${RT:-0},\"relay_rss\":${RR:-0},\"relay_up\":$([ -n "$RP" ] && echo true || echo false),\"mem_total\":$MT,\"mem_free\":$MF,\"mem_buffers\":$MB,\"mem_cached\":$MC,\"wan_rx\":$WR,\"wan_tx\":$WT,\"lan_rx\":$LR,\"lan_tx\":$LT,\"load1\":\"$L1\",\"load5\":\"$L5\",\"load15\":\"$L15\",\"conn\":${CC:-0},\"conn_max\":${CM:-0},\"temp\":${TEMP:-0},\"sys_uptime\":$UPS}"
