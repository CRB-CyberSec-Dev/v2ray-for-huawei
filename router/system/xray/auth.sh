# sourced by the panel CGIs: session check for the login added on top of the panel
# sessions live in RAM (/tmp), so a reboot logs everyone out
SESS=/tmp/xraypanel
SESS_IDLE=3600      # log out after 1h without any panel request
SESS_MAX=86400      # and always after 24h

session_token() {
  busybox echo "; $HTTP_COOKIE" | busybox sed -n 's/.*; *xps=\([0-9a-f]\{32\}\).*/\1/p'
}

auth_ok() {
  local tok f now created last
  tok=$(session_token)
  [ -n "$tok" ] || return 1
  f="$SESS/$tok"
  [ -f "$f" ] || return 1
  now=$(busybox date +%s)
  created=$(busybox cat "$f" 2>/dev/null)
  last=$(busybox stat -c %Y "$f" 2>/dev/null)
  if [ -z "$created" ] || [ -z "$last" ] || [ $((now-created)) -gt $SESS_MAX ] || [ $((now-last)) -gt $SESS_IDLE ]; then
    busybox rm -f "$f"
    return 1
  fi
  busybox touch "$f"
  return 0
}

require_auth() {
  auth_ok && return 0
  printf 'HTTP/1.0 401 Unauthorized\r\nContent-Type: text/plain\r\nCache-Control: no-store\r\n\r\nlogin required\n'
  exit 0
}
