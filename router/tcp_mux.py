"""
CECLAW TCP Multiplexer
port 8000 統一入口：
  CONNECT → asyncio CONNECT proxy handler（HTTPS tunnel）
  其他    → 轉發至 uvicorn (127.0.0.1:8080)
"""
import asyncio
import logging

logger = logging.getLogger("ceclaw.tcp_mux")

ALLOWED_DOMAINS: list[str] = []

UVICORN_HOST = "127.0.0.1"
UVICORN_PORT = 18080
CONNECT_TIMEOUT = 30.0
BUFFER = 65536


def _check_allowed(host: str) -> bool:
    if not ALLOWED_DOMAINS:
        return True
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            data = await asyncio.wait_for(reader.read(BUFFER), timeout=CONNECT_TIMEOUT)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        if not writer.is_closing():
            writer.close()


async def _handle_connect(client_r, client_w, host, port):
    peer = client_w.get_extra_info("peername", ("?", 0))[0]
    if not _check_allowed(host):
        logger.warning(f"[proxy] CONNECT {host}:{port} → 403 BLOCKED (peer={peer})")
        client_w.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        await client_w.drain()
        client_w.close()
        return
    try:
        remote_r, remote_w = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
        )
    except Exception as e:
        logger.warning(f"[proxy] CONNECT {host}:{port} → 502 ({e}) (peer={peer})")
        client_w.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await client_w.drain()
        client_w.close()
        return
    logger.info(f"[proxy] CONNECT {host}:{port} → 200 (peer={peer})")
    client_w.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await client_w.drain()
    await asyncio.gather(
        _pipe(client_r, remote_w),
        _pipe(remote_r, client_w),
        return_exceptions=True,
    )


async def _forward_to_uvicorn(client_r, client_w, first_chunk):
    try:
        remote_r, remote_w = await asyncio.wait_for(
            asyncio.open_connection(UVICORN_HOST, UVICORN_PORT),
            timeout=CONNECT_TIMEOUT,
        )
    except Exception as e:
        logger.warning(f"[mux] uvicorn forward failed: {e}")
        if not client_w.is_closing():
            client_w.close()
        return
    remote_w.write(first_chunk)
    await remote_w.drain()
    await asyncio.gather(
        _pipe(client_r, remote_w),
        _pipe(remote_r, client_w),
        return_exceptions=True,
    )


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        first = await asyncio.wait_for(reader.read(65536), timeout=10.0)
    except asyncio.TimeoutError:
        writer.close()
        return
    if not first:
        writer.close()
        return
    first_line = first.split(b"\r\n", 1)[0]
    parts = first_line.split(b" ")
    if len(parts) >= 2 and parts[0] == b"CONNECT":
        target = parts[1].decode(errors="replace")
        if ":" in target:
            host, port_str = target.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 443
        else:
            host, port = target, 443
        await _handle_connect(reader, writer, host, port)
    else:
        await _forward_to_uvicorn(reader, writer, first)


async def run_tcp_mux(host: str = "0.0.0.0", port: int = 8000):
    server = await asyncio.start_server(_handle, host, port)
    logger.info(f"[mux] TCP mux listening on {host}:{port}")
    logger.info(f"[mux] CONNECT → proxy | HTTP → uvicorn:{UVICORN_PORT}")
    async with server:
        await server.serve_forever()
