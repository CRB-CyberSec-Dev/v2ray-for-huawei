#!/system/bin/busybox ash
. /system/xray/auth.sh
require_auth
DIR=/system/xray
ST=/data/xray
CONF=$ST/xray.conf

urldecode() {
  busybox echo "$1" | busybox sed 's/+/ /g' | busybox httpd -d -
}
# busybox httpd -d expects a literal arg, not stdin; use arg form instead
urldecode() {
  local s
  s=$(busybox echo "$1" | busybox sed 's/+/ /g')
  busybox httpd -d "$s"
}

shq() {
  busybox echo "$1" | busybox sed "s/'/'\\\\''/g"
}

getparam() {
  # getparam NAME QUERYSTRING
  local name="$1" qs="$2" piece k v found
  found=""
  local oldifs="$IFS"
  IFS='&'
  for piece in $qs; do
    k=${piece%%=*}
    v=${piece#*=}
    if [ "$k" = "$name" ]; then
      found=$(urldecode "$v")
    fi
  done
  IFS="$oldifs"
  busybox echo "$found"
}

QS="$QUERY_STRING"

LINK=$(getparam link "$QS")
PIN_OVERRIDE=$(getparam pin "$QS")

if [ -n "$LINK" ]; then
  SCHEME=${LINK%%://*}
  REST=${LINK#*://}
  BEFORE_HASH=${REST%%#*}
  case "$BEFORE_HASH" in
    *\?*) HOSTPART=${BEFORE_HASH%%\?*}; LQS=${BEFORE_HASH#*\?} ;;
    *) HOSTPART=$BEFORE_HASH; LQS="" ;;
  esac
  case "$HOSTPART" in
    *@*) USERINFO=${HOSTPART%%@*}; HOSTPORT=${HOSTPART#*@} ;;
    *) USERINFO=""; HOSTPORT=$HOSTPART ;;
  esac
  HOST=${HOSTPORT%:*}
  PORT=${HOSTPORT##*:}

  SECURITY=$(getparam security "$LQS")
  SNI=$(getparam sni "$LQS")
  [ -z "$SNI" ] && SNI=$(getparam peer "$LQS")
  FP=$(getparam fp "$LQS")
  [ -z "$FP" ] && FP=chrome
  NETWORK=$(getparam type "$LQS")
  [ -z "$NETWORK" ] && NETWORK=tcp
  WSPATH=$(getparam path "$LQS")
  WSHOST=$(getparam host "$LQS")

  case "$SCHEME" in
    trojan)
      PROTO=trojan
      SECRET=$USERINFO
      [ -z "$SECURITY" ] && SECURITY=tls
      SSMETHOD=""
      ;;
    vless)
      PROTO=vless
      SECRET=$USERINFO
      [ -z "$SECURITY" ] && SECURITY=none
      SSMETHOD=""
      ;;
    ss)
      PROTO=shadowsocks
      DEC=$(busybox echo "$USERINFO" | busybox base64 -d 2>/dev/null)
      case "$DEC" in
        *:*) USERINFO=$DEC ;;
      esac
      SSMETHOD=${USERINFO%%:*}
      SECRET=${USERINFO#*:}
      SECURITY=none
      ;;
    *)
      echo "Status: 400 Bad Request"
      echo "Content-Type: text/plain"
      echo ""
      echo "unsupported scheme: $SCHEME (supported: trojan, vless, ss). For vmess, use manual fields."
      exit 0
      ;;
  esac
else
  PROTO=$(getparam proto "$QS")
  HOST=$(getparam addr "$QS")
  PORT=$(getparam port "$QS")
  SECRET=$(getparam secret "$QS")
  SSMETHOD=$(getparam ssmethod "$QS")
  NETWORK=$(getparam network "$QS")
  [ -z "$NETWORK" ] && NETWORK=tcp
  SECURITY=$(getparam security "$QS")
  [ -z "$SECURITY" ] && SECURITY=none
  SNI=$(getparam sni "$QS")
  FP=$(getparam fp "$QS")
  [ -z "$FP" ] && FP=chrome
  WSPATH=$(getparam wspath "$QS")
  WSHOST=$(getparam wshost "$QS")
fi

if [ -n "$PIN_OVERRIDE" ]; then
  PIN=$PIN_OVERRIDE
elif [ -f "$CONF" ]; then
  # no pin submitted this time - keep whatever was already configured
  PIN=$(. "$CONF"; busybox echo "$PIN")
fi

if [ -z "$SECRET" ] && [ -f "$CONF" ]; then
  SECRET=$(. "$CONF"; busybox echo "$SECRET")
fi

if [ -z "$HOST" ] || [ -z "$PORT" ] || [ -z "$SECRET" ]; then
  echo "Status: 400 Bad Request"
  echo "Content-Type: text/plain"
  echo ""
  echo "missing required fields (need server address, port, secret)"
  exit 0
fi


busybox cat > "$CONF" <<EOF
PROTO='$(shq "$PROTO")'
ADDR='$(shq "$HOST")'
PORT='$(shq "$PORT")'
SECRET='$(shq "$SECRET")'
SSMETHOD='$(shq "$SSMETHOD")'
NETWORK='$(shq "$NETWORK")'
SECURITY='$(shq "$SECURITY")'
SNI='$(shq "$SNI")'
FP='$(shq "$FP")'
WSPATH='$(shq "$WSPATH")'
WSHOST='$(shq "$WSHOST")'
PIN='$(shq "$PIN")'
EOF

OLD_REDIRECT=no
[ -f "$ST/redirect_state" ] && OLD_REDIRECT=$(busybox cat "$ST/redirect_state")
busybox echo "REDIRECT_ENABLE=$OLD_REDIRECT" >> "$CONF"

busybox echo 1 > "$ST/tunnel_state"
"$DIR/restart.sh" > "$ST/last_restart.log" 2>&1

echo "Content-Type: text/plain"
echo ""
echo "saved: proto=$PROTO addr=$HOST port=$PORT network=$NETWORK security=$SECURITY"
busybox cat "$ST/last_restart.log"
