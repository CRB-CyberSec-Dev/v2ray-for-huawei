#!/system/bin/busybox ash
. /system/xray/auth.sh
require_auth
DIR=/system/xray
ST=/data/xray
QS="$QUERY_STRING"
ACTION=""
case "$QS" in
  action=*) ACTION=${QS#action=} ;;
esac
ACTION=${ACTION%%&*}


echo "Content-Type: text/plain"
echo "Cache-Control: no-store"
echo ""

xray_up() { busybox ps | busybox grep '/system/xray/xray run' | busybox grep -v grep >/dev/null; }

case "$ACTION" in
  start)
    busybox echo 1 > "$ST/tunnel_state"
    "$DIR/start.sh" >/dev/null 2>&1
    echo "tunnel started"
    ;;
  stop)
    "$DIR/redirect_off.sh" >/dev/null 2>&1
    busybox echo 0 > "$ST/redirect_state"
    busybox echo 0 > "$ST/tunnel_state"
    "$DIR/udp_untunnel.sh" >/dev/null 2>&1
    [ "$(busybox cat "$ST/udp_mode" 2>/dev/null)" = "tunnel" ] && busybox echo direct > "$ST/udp_mode"
    "$DIR/stop.sh" >/dev/null 2>&1
    echo "tunnel stopped, LAN redirect turned off"
    ;;
  restart)
    busybox echo 1 > "$ST/tunnel_state"
    "$DIR/restart.sh" >/dev/null 2>&1
    echo "tunnel restarted"
    ;;
  redirect_on)
    if ! xray_up; then
      echo "refused: start the tunnel first"
    else
      "$DIR/redirect_on.sh" >/dev/null 2>&1
      busybox echo 1 > "$ST/redirect_state"
      echo "LAN redirect enabled"
    fi
    ;;
  redirect_off)
    "$DIR/redirect_off.sh" >/dev/null 2>&1
    busybox echo 0 > "$ST/redirect_state"
    echo "LAN redirect disabled"
    ;;
  udp_tunnel)
    if ! xray_up; then
      echo "refused: start the tunnel first"
    else
      "$DIR/udp_tunnel.sh" >/dev/null 2>&1
      busybox echo tunnel > "$ST/udp_mode"
      echo "LAN UDP is now tunneled"
    fi
    ;;
  udp_block)
    "$DIR/udp_untunnel.sh" >/dev/null 2>&1
    "$DIR/udp_block.sh" >/dev/null 2>&1
    busybox echo block > "$ST/udp_mode"
    echo "LAN UDP blocked (DNS still allowed)"
    ;;
  udp_direct)
    "$DIR/udp_untunnel.sh" >/dev/null 2>&1
    "$DIR/udp_unblock.sh" >/dev/null 2>&1
    busybox echo direct > "$ST/udp_mode"
    echo "LAN UDP goes direct"
    ;;
  cipher_fast|cipher_compat)
    busybox echo "${ACTION#cipher_}" > "$ST/cipher_mode"
    if xray_up; then
      "$DIR/restart.sh" >/dev/null 2>&1
    else
      "$DIR/gen_config.sh" >/dev/null 2>&1
    fi
    [ "$ACTION" = cipher_fast ] && echo "encryption: fast (TLS 1.3, ChaCha20)" || echo "encryption: compatible (TLS 1.3, AES-GCM)"
    ;;
  *)
    echo "unknown action: $ACTION"
    ;;
esac
