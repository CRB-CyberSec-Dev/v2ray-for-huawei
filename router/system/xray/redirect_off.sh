#!/system/bin/busybox ash
CHAIN=XRAY_REDIRECT
iptables -t nat -D PREROUTING -i br0 -p tcp -j $CHAIN 2>/dev/null
iptables -t nat -D PREROUTING -i br0 -p udp -j $CHAIN 2>/dev/null
iptables -t nat -F $CHAIN 2>/dev/null
iptables -t nat -X $CHAIN 2>/dev/null
echo "redirect disabled"
