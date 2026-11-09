# 临时联调脚本，验证完删除；不属于项目交付物
import socket
import threading
import time
import json
import sys

HOST, PORT = "127.0.0.1", 9000

def recv_loop(conn):
    buf = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                print(f"[收到] {line.decode('utf-8', 'replace')}")

def send_menu(conn):
    """手动输入命令，向边缘机发包验证 A3"""
    while True:
        cmd = input(
            "\n发送什么？\n"
            "  1 = recognize\n"
            "  2 = version_query\n"
            "  3 = 非法 JSON\n"
            "  4 = 未知 type\n"
            "  5 = 半包（分两次发）\n"
            "  6 = 超长帧（1MB+）\n"
            "  0 = 退出\n"
            "> ").strip()
        if cmd == "0":
            conn.close()
            sys.exit(0)
        if cmd == "1":
            conn.sendall(b'{"type":"recognize","request_id":"r-test-001"}\n')
        elif cmd == "2":
            conn.sendall(b'{"type":"version_query"}\n')
        elif cmd == "3":
            conn.sendall(b'not a json\n')
        elif cmd == "4":
            conn.sendall(b'{"type":"foo"}\n')
        elif cmd == "5":
            conn.sendall(b'{"type":"recog')
            time.sleep(0.3)
            conn.sendall(b'nize","request_id":"r-half"}\n')
        elif cmd == "6":
            conn.sendall(b'x' * (1024 * 1024 + 1) + b'\n')
            time.sleep(0.1)
            conn.sendall(b'{"type":"version_query"}\n')  # 超长后的恢复验证

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((HOST, PORT))
srv.listen(1)
print(f"[Server] 监听 {HOST}:{PORT}，等待边缘机连接...")

while True:
    conn, addr = srv.accept()
    print(f"[Server] 边缘机已连接：{addr}")
    threading.Thread(target=recv_loop, args=(conn,), daemon=True).start()
    try:
        send_menu(conn)
    except (EOFError, KeyboardInterrupt):
        print("\n[Server] 退出")
        break