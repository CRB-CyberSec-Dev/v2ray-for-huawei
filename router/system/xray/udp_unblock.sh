#!/system/bin/busybox ash
CHAIN=XRAY_UDPBLOCK
iptables -t filter -D FORWARD -i br0 -p udp -j $CHAIN 2>/dev/null
iptables -t filter -F $CHAIN 2>/dev/null
iptables -t filter -X $CHAIN 2>/dev/null
echo "udp direct"
