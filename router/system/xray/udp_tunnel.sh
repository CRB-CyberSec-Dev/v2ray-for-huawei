#!/system/bin/busybox ash
# Tunnel LAN UDP: redirect to udprelay (port 12346), which forwards via xray SOCKS UDP.
DIR=/system/xray
ST=/data/xray
CHAIN=XRAY_UDPREDIR
"$DIR/udp_unblock.sh" >/dev/null 2>&1
if ! busybox ps | busybox grep '/system/xray/udprelay' | busybox grep -v grep >/dev/null; then
  export GOMEMLIMIT=16MiB GOGC=40 GOMAXPROCS=1
  busybox setsid "$DIR/udprelay" > "$ST/udprelay.log" 2>&1 < /dev/null &
  busybox sleep 1
fi
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
iptables -t nat -A $CHAIN -d 255.255.255.255 -j RETURN
iptables -t nat -A $CHAIN -p udp -j REDIRECT --to-ports 12346
iptables -t nat -I PREROUTING 1 -i br0 -p udp -j $CHAIN
echo "udp tunneled"
