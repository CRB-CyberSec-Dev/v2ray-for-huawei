#!/system/bin/busybox ash
# Enable whole-LAN transparent TCP+UDP redirection into xray's dokodemo-door inbound (port 12345).
CHAIN=XRAY_REDIRECT

# wipe any previous instance of our chain (idempotent)
iptables -t nat -D PREROUTING -i br0 -p tcp -j $CHAIN 2>/dev/null
iptables -t nat -D PREROUTING -i br0 -p udp -j $CHAIN 2>/dev/null
iptables -t nat -F $CHAIN 2>/dev/null
iptables -t nat -X $CHAIN 2>/dev/null

iptables -t nat -N $CHAIN
iptables -t nat -A $CHAIN -d 192.168.0.0/16 -j RETURN
iptables -t nat -A $CHAIN -d 10.0.0.0/8 -j RETURN
iptables -t nat -A $CHAIN -d 172.16.0.0/12 -j RETURN
iptables -t nat -A $CHAIN -d 127.0.0.0/8 -j RETURN
iptables -t nat -A $CHAIN -d 169.254.0.0/16 -j RETURN
iptables -t nat -A $CHAIN -d 224.0.0.0/4 -j RETURN
iptables -t nat -A $CHAIN -p tcp -j REDIRECT --to-ports 12345

iptables -t nat -I PREROUTING 1 -i br0 -p tcp -j $CHAIN

echo "redirect enabled (tcp only)"
