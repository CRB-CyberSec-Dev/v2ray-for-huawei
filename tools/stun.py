import socket,os,struct
for host in [("stun.l.google.com",19302),("stun.cloudflare.com",3478)]:
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(6)
    req=struct.pack(">HHI",1,0,0x2112A442)+os.urandom(12)
    try:
        s.sendto(req,host); d,_=s.recvfrom(2048)
        i=20
        while i<len(d):
            t,l=struct.unpack(">HH",d[i:i+4])
            if t==0x0020:
                ip=[b^m for b,m in zip(d[i+8:i+12],bytes.fromhex("2112A442"))]
                print(host[0],"-> reflexive IP",".".join(map(str,ip)))
            i+=4+l+((4-l%4)%4)
    except Exception as e: print(host[0],"FAIL",repr(e))
