#!/system/bin/busybox ash
# /system is read-only after boot, so all config, state and logs live in $ST (/data is rw and persistent)
DIR=/system/xray
ST=/data/xray
busybox mkdir -p "$ST"
busybox chmod 700 "$ST"
exec > "$ST/boot.log" 2>&1

busybox setsid busybox httpd -f -p 0.0.0.0:8081 -h "$DIR/www" > "$ST/httpd.log" 2>&1 < /dev/null &

TS=1
[ -f "$ST/tunnel_state" ] && TS=$(busybox cat "$ST/tunnel_state")
if [ "$TS" != "0" ]; then
  "$DIR/start.sh" > "$ST/boot_start.log" 2>&1
fi

if [ -f "$ST/udp_mode" ] && [ "$(busybox cat "$ST/udp_mode")" = "tunnel" ] && [ "$TS" != "0" ]; then
  "$DIR/udp_tunnel.sh" >> "$ST/boot_start.log" 2>&1
fi

if [ -f "$ST/udp_mode" ] && [ "$(busybox cat "$ST/udp_mode")" = "block" ]; then
  "$DIR/udp_block.sh" >> "$ST/boot_start.log" 2>&1
fi

if [ -f "$ST/redirect_state" ]; then
  RS=$(busybox cat "$ST/redirect_state")
  if [ "$RS" = "1" ]; then
    "$DIR/redirect_on.sh" >> "$ST/boot_start.log" 2>&1
  fi
fi

busybox setsid "$DIR/watchdog.sh" > "$ST/watchdog_stdout.log" 2>&1 < /dev/null &
