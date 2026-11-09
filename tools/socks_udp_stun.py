import socket,struct,os
ROUTER=os.environ.get("ROUTER","192.168.8.1")
# SOCKS5 UDP ASSOCIATE through the router's xray, then STUN query via the tunnel
c=socket.create_connection((ROUTER,1080),timeout=8)
c.sendall(b"\x05\x01\x00"); assert c.recv(2)==b"\x05\x00"
c.sendall(b"\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00")
r=c.recv(64); port=struct.unpack(">H",r[8:10])[0]
u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); u.settimeout(8)
req=struct.pack(">HHI",1,0,0x2112A442)+os.urandom(12)
for name,p in [("stun.l.google.com",19302),("stun.cloudflare.com",3478)]:
    ip=socket.gethostbyname(name)
    hdr=b"\x00\x00\x00\x01"+socket.inet_aton(ip)+struct.pack(">H",p)
    u.sendto(hdr+req,(ROUTER,port))
    try:
        d,_=u.recvfrom(2048); d=d[10:]; i=20
        while i<len(d):
            t,l=struct.unpack(">HH",d[i:i+4])
            if t==0x0020:
                x=[b^m for b,m in zip(d[i+8:i+12],bytes.fromhex("2112A442"))]
                print(name,"via tunnel UDP ->",".".join(map(str,x)))
            i+=4+l+((4-l%4)%4)
    except Exception as e: print(name,"FAIL",repr(e))
