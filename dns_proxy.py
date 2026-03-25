#!/usr/bin/env python3
import socket,struct,urllib.request,json,threading
ROUTER_URL="http://host.openshell.internal:8000/v1/dns"
HTTP_PROXY="http://10.200.0.1:3128"
def parse_dns_name(data,offset):
    labels=[]
    while True:
        length=data[offset]
        if length==0: offset+=1; break
        if length&0xC0==0xC0:
            ptr=((length&0x3F)<<8)|data[offset+1]
            name,_=parse_dns_name(data,ptr); labels.append(name); offset+=2; break
        offset+=1; labels.append(data[offset:offset+length].decode()); offset+=length
    return ".".join(labels),offset
def build_dns_response(request,addresses):
    tid=request[:2]; flags=b'\x81\x80'; counts=struct.pack(">HHHH",1,len(addresses),0,0)
    offset=12
    while request[offset]!=0:
        if request[offset]&0xC0==0xC0: offset+=2; break
        offset+=request[offset]+1
    offset+=5; question=request[12:offset]; answers=b""
    for ip in addresses:
        answers+=b'\xc0\x0c'+struct.pack(">HHIH",1,1,60,4)+socket.inet_aton(ip)
    return tid+flags+counts+question+answers
def resolve(name):
    try:
        proxy=urllib.request.ProxyHandler({"http":HTTP_PROXY})
        opener=urllib.request.build_opener(proxy)
        with opener.open(f"{ROUTER_URL}?name={name}",timeout=5) as r:
            return json.loads(r.read()).get("addresses",[])
    except: return []
def handle(sock,data,addr):
    try:
        name,_=parse_dns_name(data,12); addrs=resolve(name)
        if addrs: sock.sendto(build_dns_response(data,addrs),addr)
        else:
            tid=data[:2]; flags=b'\x81\x83'; counts=struct.pack(">HHHH",1,0,0,0)
            offset=12
            while data[offset]!=0: offset+=data[offset]+1
            offset+=5; sock.sendto(tid+flags+counts+data[12:offset],addr)
    except: pass
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
sock.bind(("127.0.0.1",53))
print("[dns_proxy] listening on 127.0.0.1:53",flush=True)
while True:
    try:
        data,addr=sock.recvfrom(512)
        threading.Thread(target=handle,args=(sock,data,addr),daemon=True).start()
    except: pass
