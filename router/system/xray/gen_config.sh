#!/system/bin/busybox ash
# Generates /data/xray/config.json from /data/xray/xray.conf
ST=/data/xray
CONF=$ST/xray.conf
OUT=$ST/config.json
[ -f "$CONF" ] || exit 1
. "$CONF"

esc() { busybox echo "$1" | busybox sed 's/\\/\\\\/g; s/"/\\"/g'; }

# default fp/network/security if unset
[ -z "$FP" ] && FP=chrome
[ -z "$NETWORK" ] && NETWORK=tcp
[ -z "$SECURITY" ] && SECURITY=none
# cipher_mode: fast = "chrome-chacha" (patched xray: Chrome hello without AES suites, so the server
# must pick ChaCha20-Poly1305, 3.5x faster than AES-GCM on this AES-less Cortex-A9); compat = uTLS $FP.
# Both are TLS 1.3.
CIPHER=$(busybox cat "$ST/cipher_mode" 2>/dev/null)
[ -z "$CIPHER" ] && CIPHER=fast

A_ADDR=$(esc "$ADDR")
A_SECRET=$(esc "$SECRET")
A_SNI=$(esc "$SNI")
A_FP=$(esc "$FP")
A_WSPATH=$(esc "$WSPATH")
A_WSHOST=$(esc "$WSHOST")
A_PIN=$(esc "$PIN")
A_SSMETHOD=$(esc "$SSMETHOD")

# stream settings block (shared by proxy outbound)
build_stream() {
  busybox echo -n "\"network\": \"$NETWORK\""
  if [ "$NETWORK" = "ws" ]; then
    busybox echo -n ", \"wsSettings\": { \"path\": \"${A_WSPATH:-/}\""
    if [ -n "$WSHOST" ]; then
      busybox echo -n ", \"headers\": { \"Host\": \"$A_WSHOST\" }"
    fi
    busybox echo -n " }"
  fi
  if [ "$SECURITY" = "tls" ]; then
    busybox echo -n ", \"security\": \"tls\", \"tlsSettings\": { \"serverName\": \"$A_SNI\", \"allowInsecure\": false"
    if [ "$CIPHER" = "fast" ]; then
      busybox echo -n ", \"fingerprint\": \"chrome-chacha\""
    else
      busybox echo -n ", \"fingerprint\": \"$A_FP\""
    fi
    if [ -n "$PIN" ]; then
      busybox echo -n ", \"pinnedPeerCertSha256\": \"$A_PIN\""
    fi
    busybox echo -n " }"
  else
    busybox echo -n ", \"security\": \"none\""
  fi
}

build_outbound_settings() {
  case "$PROTO" in
    trojan)
      busybox echo -n "{ \"servers\": [ { \"address\": \"$A_ADDR\", \"port\": $PORT, \"password\": \"$A_SECRET\" } ] }"
      ;;
    vless)
      busybox echo -n "{ \"vnext\": [ { \"address\": \"$A_ADDR\", \"port\": $PORT, \"users\": [ { \"id\": \"$A_SECRET\", \"encryption\": \"none\" } ] } ] }"
      ;;
    shadowsocks)
      busybox echo -n "{ \"servers\": [ { \"address\": \"$A_ADDR\", \"port\": $PORT, \"method\": \"$A_SSMETHOD\", \"password\": \"$A_SECRET\" } ] }"
      ;;
    *)
      busybox echo -n "{}"
      ;;
  esac
}

if [ -n "$PROTO" ] && [ -n "$ADDR" ] && [ -n "$PORT" ]; then
  PROXY_TAG=proxy
  OUTBOUND_PROXY_BLOCK=$(busybox cat <<EOF
    {
      "tag": "proxy",
      "protocol": "$PROTO",
      "settings": $(build_outbound_settings),
      "streamSettings": { $(build_stream) },
      "mux": { "enabled": false }
    },
EOF
)
  SERVER_EXCEPTION_RULE=", { \"type\": \"field\", \"domain\": [\"$A_ADDR\"], \"outboundTag\": \"direct\" }"
else
  PROXY_TAG=direct
  OUTBOUND_PROXY_BLOCK=""
  SERVER_EXCEPTION_RULE=""
fi

busybox cat > "$OUT" <<EOF
{
  "log": { "loglevel": "warning", "access": "none" },
  "inbounds": [
    { "listen": "0.0.0.0", "port": 1080, "protocol": "socks", "settings": { "auth": "noauth", "udp": true }, "tag": "socks-in" },
    { "listen": "0.0.0.0", "port": 1081, "protocol": "http", "tag": "http-in" },
    { "listen": "0.0.0.0", "port": 12345, "protocol": "dokodemo-door", "settings": { "network": "tcp", "followRedirect": true }, "tag": "redirect-in" }
  ],
  "outbounds": [
    $OUTBOUND_PROXY_BLOCK
    { "tag": "direct", "protocol": "freedom" },
    { "tag": "block", "protocol": "blackhole" }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      { "type": "field", "ip": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16"], "outboundTag": "direct" }
      $SERVER_EXCEPTION_RULE,
      { "type": "field", "network": "tcp,udp", "outboundTag": "$PROXY_TAG" }
    ]
  }
}
EOF

echo "config written to $OUT"
