#!/system/bin/busybox ash
# Panel login using the router's own admin account, checked by the Huawei web UI login API
# (password_type 4). Same scheme as the router's login page, so the password never crosses
# the network:
#   GET  ?challenge        -> we open a router web session and hand the browser its one-time token
#   POST c=<id>&u=<user>&h=<hash>   hash = base64(sha256hex(user + base64(sha256hex(password)) + token))
# On success we log that router session straight back out and give the browser a panel session cookie.
set -f
. /system/xray/auth.sh
CH="$SESS/ch"
CH_TTL=120          # a challenge must be answered within 2 minutes
CH_MAX=20           # pending challenges at once

reply() {
  busybox echo "Content-Type: application/json"
  busybox echo "Cache-Control: no-store"
  [ -n "$3" ] && busybox echo "$3"
  busybox echo ""
  busybox echo "{\"ok\":$1,$2}"
  exit 0
}
fail() { reply false "\"msg\":\"$1\""; }

urldecode() {
  local s
  s=$(printf '%s' "$1" | busybox sed 's/+/ /g')
  s=$(busybox httpd -d "x$s")
  printf '%s' "${s#x}"
}

getparam() {
  local name="$1" piece found="" oldifs="$IFS"
  IFS='&'
  for piece in $BODY; do
    [ "${piece%%=*}" = "$name" ] && found=${piece#*=}
  done
  IFS="$oldifs"
  urldecode "$found"
}

newid() { busybox dd if=/dev/urandom bs=16 count=1 2>/dev/null | busybox od -An -tx1 | busybox tr -d ' \n'; }
xmlesc() { printf '%s' "$1" | busybox sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
hdr() { busybox echo "$1" | busybox grep -i "^$2:" | busybox head -1 | busybox sed 's/^[^:]*: *//' | busybox tr -d '\r'; }

# hw METHOD PATH COOKIE TOKEN BODY -> raw HTTP response from the router web UI
hw() {
  {
    printf '%s %s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n' "$1" "$2" "$H"
    [ -n "$3" ] && printf 'Cookie: %s\r\n' "$3"
    [ -n "$4" ] && printf '__RequestVerificationToken: %s\r\n' "$4"
    if [ "$1" = POST ]; then
      printf 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8\r\nX-Requested-With: XMLHttpRequest\r\nContent-Length: %s\r\n\r\n%s' "${#5}" "$5"
    else
      printf '\r\n'
    fi
  } | busybox nc -w 5 "$H" 80
}

# drop files in dir $1 older than $2 seconds (by mtime)
expire() {
  local f now
  now=$(busybox date +%s)
  set +f
  for f in "$1"/*; do
    [ -f "$f" ] || continue
    [ $((now-$(busybox stat -c %Y "$f" 2>/dev/null || echo 0))) -gt "$2" ] && busybox rm -f "$f"
  done
  set -f
}

# the router web UI only answers on its LAN address (127.0.0.1 gets redirected)
H=$(busybox ifconfig br0 2>/dev/null | busybox sed -n 's/.*inet addr:\([0-9.]*\).*/\1/p')
[ -z "$H" ] && H=192.168.8.1

busybox mkdir -p "$CH"
busybox chmod 700 "$SESS" "$CH"

# ---- step 1: challenge ----
if [ "$REQUEST_METHOD" = "GET" ] && [ "$QUERY_STRING" = "challenge" ]; then
  expire "$CH" $CH_TTL
  set +f; N=$(busybox ls "$CH" | busybox wc -l); set -f
  [ "$N" -lt $CH_MAX ] || fail "Too many login attempts in progress, wait a minute"
  R=$(hw GET /api/webserver/SesTokInfo)
  SES=$(busybox echo "$R" | busybox sed -n 's:.*<SesInfo>\(.*\)</SesInfo>.*:\1:p')
  TOK=$(busybox echo "$R" | busybox sed -n 's:.*<TokInfo>\(.*\)</TokInfo>.*:\1:p')
  [ -n "$SES" ] && [ -n "$TOK" ] || fail "Router login service did not answer, try again"
  ID=$(newid)
  [ ${#ID} -eq 32 ] || fail "could not create challenge"
  printf '%s\n%s\n' "$SES" "$TOK" > "$CH/$ID"
  reply true "\"c\":\"$ID\",\"t\":\"$TOK\""
fi

# ---- step 2: hashed login ----
[ "$REQUEST_METHOD" = "POST" ] || fail "bad request"
LEN=${CONTENT_LENGTH:-0}
{ [ "$LEN" -gt 0 ] && [ "$LEN" -le 1024 ]; } 2>/dev/null || fail "bad request"
BODY=$(busybox head -c "$LEN")

CID=$(getparam c)
USERNAME=$(getparam u)
PW=$(getparam h)
busybox echo "$CID" | busybox grep -qE '^[0-9a-f]{32}$' || fail "Login expired, try again"
busybox echo "$PW" | busybox grep -qE '^[A-Za-z0-9+/]{86}==$' || fail "bad request"
[ -n "$USERNAME" ] || fail "Enter the router username and password"

# each challenge is single use
expire "$CH" $CH_TTL
[ -f "$CH/$CID" ] || fail "Login expired, try again"
SES=$(busybox sed -n 1p "$CH/$CID")
TOK=$(busybox sed -n 2p "$CH/$CID")
busybox rm -f "$CH/$CID"

REQ="<?xml version=\"1.0\" encoding=\"UTF-8\"?><request><Username>$(xmlesc "$USERNAME")</Username><Password>$PW</Password><password_type>4</password_type></request>"
R=$(hw POST /api/user/login "$SES" "$TOK" "$REQ")

case "$R" in
  *"<response>OK</response>"*) ;;
  *)
    busybox sleep 1
    CODE=$(busybox echo "$R" | busybox sed -n 's:.*<code>\([0-9]*\)</code>.*:\1:p')
    case "$CODE" in
      108001|108002|108006) fail "Wrong username or password" ;;
      108007) fail "Too many failed attempts. The router locked login, wait a few minutes" ;;
      108003) fail "Router says this account is already signed in. Sign out of the router web page and try again" ;;
      125002|125003) fail "Login expired, try again" ;;
      "") fail "Router login service did not answer, try again" ;;
      *) fail "Router refused the login (code $CODE)" ;;
    esac
    ;;
esac

# don't keep a router web session open on our behalf
NSES=$(hdr "$R" set-cookie | busybox sed 's/;.*//')
NTOK=$(hdr "$R" __RequestVerificationTokenone)
if [ -n "$NSES" ] && [ -n "$NTOK" ]; then
  hw POST /api/user/logout "$NSES" "$NTOK" '<?xml version="1.0" encoding="UTF-8"?><request><Logout>1</Logout></request>' >/dev/null 2>&1
fi

NOW=$(busybox date +%s)
set +f
for f in "$SESS"/*; do
  [ -f "$f" ] || continue
  C=$(busybox cat "$f" 2>/dev/null); L=$(busybox stat -c %Y "$f" 2>/dev/null)
  if [ -z "$C" ] || [ -z "$L" ] || [ $((NOW-C)) -gt $SESS_MAX ] || [ $((NOW-L)) -gt $SESS_IDLE ]; then
    busybox rm -f "$f"
  fi
done
set -f
TOKEN=$(newid)
[ ${#TOKEN} -eq 32 ] || fail "could not create session"
busybox echo "$NOW" > "$SESS/$TOKEN"
reply true "\"msg\":\"ok\"" "Set-Cookie: xps=$TOKEN; Path=/; HttpOnly; SameSite=Strict; Max-Age=$SESS_MAX"
