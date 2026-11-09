#!/system/bin/busybox ash
CHAIN=XRAY_UDPREDIR
iptables -t nat -D PREROUTING -i br0 -p udp -j $CHAIN 2>/dev/null
iptables -t nat -F $CHAIN 2>/dev/null
iptables -t nat -X $CHAIN 2>/dev/null
for p in $(busybox ps | busybox grep '/system/xray/udprelay' | busybox grep -v grep | busybox awk '{print $1}'); do busybox kill "$p" 2>/dev/null; done
echo "udp tunnel off"
