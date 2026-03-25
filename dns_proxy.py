#!/usr/bin/env python3
"""
CECLAW DNS Proxy v1.0
sandbox 內以 root 跑，監聽 127.0.0.1:53 UDP
透過 HTTP proxy 查 Router /v1/dns，解決 EAI_AGAIN 問題
"""
import socket
import struct
import urllib.request
import json
import threading

ROUTER_URL = "http://host.openshell.internal:8000/v1/dns"
HTTP_PROXY = "http://10.200.0.1:3128"
LISTEN_ADDR = "127.0.0.1"
LISTEN_PORT = 53

def parse_dns_name(data, offset):
    labels = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            ptr = ((length & 0x3F) << 8) | data[offset + 1]
            name, _ = parse_dns_name(data, ptr)
            labels.append(name)
            offset += 2
            break
        offset += 1
        labels.append(data[offset:offset+length].decode())
        offset += length
    return ".".join(labels), offset

def build_dns_response(request, addresses):
    tid = request[:2]
    flags = b'\x81\x80'
    counts = struct.pack(">HHHH", 1, len(addresses), 0, 0)
    offset = 12
    while request[offset] != 0:
        if request[offset] & 0xC0 == 0xC0:
            offset += 2
            break
        offset += request[offset] + 1
    offset += 1
    offset += 4
    question = request[12:offset]
    answers = b""
    for ip in addresses:
        answers += b'\xc0\x0c'
        answers += struct.pack(">HHIH", 1, 1, 60, 4)
        answers += socket.inet_aton(ip)
    return tid + flags + counts + question + answers

def resolve_via_router(name):
    try:
        proxy = urllib.request.ProxyHandler({"http": HTTP_PROXY})
        opener = urllib.request.build_opener(proxy)
        with opener.open(f"{ROUTER_URL}?name={name}", timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("addresses", [])
    except Exception as e:
        print(f"[dns_proxy] resolve error for {name}: {e}", flush=True)
        return []

def handle_query(sock, data, addr):
    try:
        name, _ = parse_dns_name(data, 12)
        print(f"[dns_proxy] query: {name}", flush=True)
        addresses = resolve_via_router(name)
        if addresses:
            sock.sendto(build_dns_response(data, addresses), addr)
            print(f"[dns_proxy] resolved {name} → {addresses[0]}", flush=True)
        else:
            tid = data[:2]
            flags = b'\x81\x83'
            counts = struct.pack(">HHHH", 1, 0, 0, 0)
            offset = 12
            while data[offset] != 0:
                offset += data[offset] + 1
            offset += 5
            sock.sendto(tid + flags + counts + data[12:offset], addr)
    except Exception as e:
        print(f"[dns_proxy] handle error: {e}", flush=True)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_ADDR, LISTEN_PORT))
    print(f"[dns_proxy] listening on {LISTEN_ADDR}:{LISTEN_PORT}", flush=True)
    while True:
        try:
            data, addr = sock.recvfrom(512)
            threading.Thread(target=handle_query, args=(sock, data, addr), daemon=True).start()
        except Exception as e:
            print(f"[dns_proxy] recv error: {e}", flush=True)

if __name__ == "__main__":
    main()
