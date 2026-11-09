#!/system/bin/busybox ash
DIR=/system/xray
ST=/data/xray
LOG="$ST/watchdog.log"

# only ever keep one watchdog alive
MYPID=$$
OTHERS=$(busybox ps | busybox grep 'watchdog.sh' | busybox grep -v grep | busybox grep -v "^ *$MYPID " | busybox awk '{print $1}')
for p in $OTHERS; do
  busybox kill -9 "$p" 2>/dev/null
done

trunc_if_big() {
  f="$1"
  [ -f "$f" ] || return
  sz=$(busybox wc -c < "$f" 2>/dev/null)
  [ -z "$sz" ] && return
  if [ "$sz" -gt 524288 ]; then
    busybox tail -c 65536 "$f" > "$f.tmp" 2>/dev/null && busybox mv "$f.tmp" "$f"
  fi
}

while true; do
  trunc_if_big "$ST/xray.log"
  trunc_if_big "$LOG"
  trunc_if_big "$ST/httpd.log"

  WANT=1
  [ -f "$ST/tunnel_state" ] && WANT=$(busybox cat "$ST/tunnel_state")
  RUNNING=$(busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep)
  if [ -z "$RUNNING" ] && [ "$WANT" != "0" ]; then
    busybox echo "$(busybox date) xray not running, restarting" >> "$LOG"
    "$DIR/start.sh" >> "$LOG" 2>&1
  fi

  if [ -f "$ST/redirect_state" ]; then
    RS=$(busybox cat "$ST/redirect_state")
    if [ "$RS" = "1" ]; then
      iptables -t nat -L XRAY_REDIRECT -n >/dev/null 2>&1
      if [ $? -ne 0 ]; then
        busybox echo "$(busybox date) XRAY_REDIRECT chain missing, re-applying" >> "$LOG"
        "$DIR/redirect_on.sh" >> "$LOG" 2>&1
      else
        JUMPCOUNT=$(iptables -t nat -L PREROUTING -n 2>/dev/null | busybox grep -c XRAY_REDIRECT)
        if [ "$JUMPCOUNT" -lt 1 ]; then
          busybox echo "$(busybox date) PREROUTING jump(s) to XRAY_REDIRECT missing (found $JUMPCOUNT, need 1), re-applying" >> "$LOG"
          "$DIR/redirect_on.sh" >> "$LOG" 2>&1
        fi
      fi
    fi
  fi

  if [ -f "$ST/udp_mode" ] && [ "$(busybox cat "$ST/udp_mode")" = "block" ]; then
    iptables -t filter -L XRAY_UDPBLOCK -n >/dev/null 2>&1 && iptables -t filter -L FORWARD -n 2>/dev/null | busybox grep -q XRAY_UDPBLOCK
    if [ $? -ne 0 ]; then
      busybox echo "$(busybox date) UDP block missing, re-applying" >> "$LOG"
      "$DIR/udp_block.sh" >> "$LOG" 2>&1
    fi
  fi

  if [ -f "$ST/udp_mode" ] && [ "$(busybox cat "$ST/udp_mode")" = "tunnel" ]; then
    RELAY=$(busybox ps | busybox grep '/system/xray/udprelay' | busybox grep -v grep)
    iptables -t nat -L XRAY_UDPREDIR -n >/dev/null 2>&1
    CH=$?
    if [ -z "$RELAY" ] || [ "$CH" -ne 0 ]; then
      busybox echo "$(busybox date) UDP tunnel relay/chain missing, re-applying" >> "$LOG"
      "$DIR/udp_tunnel.sh" >> "$LOG" 2>&1
    fi
  fi

  HTTPDRUNNING=$(busybox ps | busybox grep 'httpd -f -p 0.0.0.0:8081' | busybox grep -v grep)
  if [ -z "$HTTPDRUNNING" ]; then
    busybox echo "$(busybox date) panel httpd not running, restarting" >> "$LOG"
    busybox setsid busybox httpd -f -p 0.0.0.0:8081 -h "$DIR/www" > "$ST/httpd.log" 2>&1 < /dev/null &
  fi

  busybox sleep 15
done
