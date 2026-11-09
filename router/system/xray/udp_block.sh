#!/system/bin/busybox ash
# Drop LAN->WAN UDP (except DNS to anywhere and anything to private ranges) so UDP cannot leak the real IP.
CHAIN=XRAY_UDPBLOCK
iptables -t filter -D FORWARD -i br0 -p udp -j $CHAIN 2>/dev/null
iptables -t filter -F $CHAIN 2>/dev/null
iptables -t filter -X $CHAIN 2>/dev/null
iptables -t filter -N $CHAIN
iptables -t filter -A $CHAIN -p udp --dport 53 -j RETURN
iptables -t filter -A $CHAIN -d 192.168.0.0/16 -j RETURN
iptables -t filter -A $CHAIN -d 10.0.0.0/8 -j RETURN
iptables -t filter -A $CHAIN -d 172.16.0.0/12 -j RETURN
iptables -t filter -A $CHAIN -d 224.0.0.0/4 -j RETURN
iptables -t filter -A $CHAIN -j DROP
iptables -t filter -I FORWARD 1 -i br0 -p udp -j $CHAIN
echo "udp blocked"
