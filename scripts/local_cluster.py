"""Mô phỏng kiến trúc Load Balancer + nhiều máy chủ NGAY TRÊN MÁY CÁ NHÂN (không tốn tiền AWS).

    python scripts/local_cluster.py              # 2 "instance" phía sau bộ cân bằng tải ở http://127.0.0.1:8000
    python scripts/local_cluster.py --nodes 3

Mỗi "instance" là một tiến trình run_local.py riêng (cổng 8001, 8002, ...) với instance ID giả
local-node-1, local-node-2, ... Tất cả dùng chung CSDL (instance/shop.db hoặc DATABASE_URL) và chung
SECRET_KEY, giống hệt cách các EC2 dùng chung RDS. Bộ cân bằng tải ở cổng 8000 chia request kiểu
round-robin và gọi /health mỗi 2 giây như ALB, máy nào lỗi sẽ bị loại khỏi vòng quay.

Trong lúc chạy, gõ lệnh rồi Enter để mô phỏng Auto Scaling:
    +   thêm một instance (scale out)      -   gỡ instance mới nhất (scale in)
    s   xem trạng thái                     q   dừng tất cả
Mở http://127.0.0.1:8000/system/live để xem request được chia cho các instance theo thời gian thực.
"""
import argparse
import atexit
import http.client
import itertools
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "results", "cluster_logs")  # log của từng "instance"
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
              "transfer-encoding", "upgrade"}


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


class Node:
    def __init__(self, idx: int, port: int, proc: subprocess.Popen):
        self.idx, self.port, self.proc = idx, port, proc
        self.name = f"local-node-{idx}"
        self.healthy = False
        self.served = 0


class Cluster:
    def __init__(self, base_port: int, threads: int):
        self.base_port, self.threads = base_port, threads
        self.nodes: list[Node] = []
        self.lock = threading.Lock()
        self.rr = itertools.count()
        self.counter = itertools.count(1)
        self.env = dict(os.environ, DISABLE_IMDS="1", PYTHONIOENCODING="utf-8",
                        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(16))

    def add(self) -> Node:
        idx = next(self.counter)
        port = self.base_port + idx
        while port_in_use(port):
            # Thường là tiến trình còn sót từ lần chạy trước; trùng cổng trên Windows gây treo request
            print(f"[cluster] Cổng {port} đang bị chiếm, dùng cổng {port + 100}", flush=True)
            port += 100
        env = dict(self.env, INSTANCE_ID=f"local-node-{idx}", INSTANCE_AZ="local-a" if idx % 2 else "local-b")
        os.makedirs(LOG_DIR, exist_ok=True)
        log = open(os.path.join(LOG_DIR, f"local-node-{idx}.log"), "w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, "-u", os.path.join(ROOT, "run_local.py"), "--port", str(port),
                                 "--threads", str(self.threads)], cwd=ROOT, env=env,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        log.close()  # tiến trình con đã giữ bản sao handle của file
        node = Node(idx, port, proc)
        with self.lock:
            self.nodes.append(node)
        print(f"[cluster] Khởi động {node.name} ở cổng {port} (chờ health check...)", flush=True)
        return node

    def remove_last(self) -> None:
        with self.lock:
            if len(self.nodes) <= 1:
                print("[cluster] Giữ tối thiểu 1 instance (giống MinSize = 1).")
                return
            node = self.nodes.pop()
        # Giống ALB deregistration: gỡ khỏi vòng quay trước, đợi request đang xử lý xong rồi mới tắt
        time.sleep(1)
        node.proc.terminate()
        print(f"[cluster] Đã gỡ {node.name} (đã phục vụ {node.served} request)", flush=True)

    def pick(self) -> Node | None:
        with self.lock:
            healthy = [n for n in self.nodes if n.healthy]
        return healthy[next(self.rr) % len(healthy)] if healthy else None

    @staticmethod
    def check(n: Node) -> None:
        ok = False
        try:
            c = http.client.HTTPConnection("127.0.0.1", n.port, timeout=2)
            c.request("GET", "/health")
            ok = c.getresponse().status == 200
            c.close()
        except OSError:
            pass
        if ok != n.healthy:
            n.healthy = ok
            print(f"[health] {n.name}: {'HEALTHY, bắt đầu nhận request' if ok else 'UNHEALTHY, ngừng chia request'}",
                  flush=True)

    def health_loop(self) -> None:
        while True:
            with self.lock:
                nodes = list(self.nodes)
            # Kiểm tra song song: trên Windows một cổng chưa mở phải ~2 giây mới báo "connection refused"
            checks = [threading.Thread(target=self.check, args=(n,), daemon=True) for n in nodes]
            for t in checks:
                t.start()
            for t in checks:
                t.join()
            time.sleep(1)

    def status(self) -> None:
        with self.lock:
            nodes = list(self.nodes)
        print(f"[cluster] {len(nodes)} instance:")
        for n in nodes:
            print(f"   {n.name:<14} cổng {n.port}  {'healthy  ' if n.healthy else 'unhealthy'}  {n.served} request")

    def stop_all(self) -> None:
        with self.lock:
            nodes, self.nodes = list(self.nodes), []
        for n in nodes:
            n.proc.terminate()


def make_handler(cluster: Cluster):
    class Proxy(BaseHTTPRequestHandler):
        def _forward(self):
            node = cluster.pick()
            if node is None:
                self.send_error(503, "Khong co instance healthy")
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
            headers["X-Forwarded-For"] = self.client_address[0]
            try:
                c = http.client.HTTPConnection("127.0.0.1", node.port, timeout=60)
                c.request(self.command, self.path, body=body, headers=headers)
                r = c.getresponse()
                data = r.read()
                c.close()
            except OSError:
                self.send_error(502, "Instance khong phan hoi")
                return
            node.served += 1
            self.send_response(r.status, r.reason)
            for k, v in r.getheaders():
                if k.lower() not in HOP_BY_HOP and k.lower() != "content-length":
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Served-By", node.name)
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _forward

        def log_message(self, *args):  # tắt log từng request cho đỡ rối màn hình
            pass

    return Proxy


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # xem chú thích trong run_local.py
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", type=int, default=2)
    ap.add_argument("--port", type=int, default=8000, help="cổng của bộ cân bằng tải")
    ap.add_argument("--threads", type=int, default=4, help="số luồng waitress mỗi instance")
    a = ap.parse_args()

    if port_in_use(a.port):
        sys.exit(f"Cổng {a.port} đang được dùng (có thể run_local.py hoặc cụm cũ vẫn đang chạy). Thử --port khác.")
    cluster = Cluster(a.port, a.threads)
    atexit.register(cluster.stop_all)  # không để sót tiến trình con giữ cổng
    first = cluster.add()
    # Đợi instance đầu tiên tạo bảng + nạp dữ liệu mẫu xong rồi mới bật các instance khác (tránh tranh chấp SQLite)
    threading.Thread(target=cluster.health_loop, daemon=True).start()
    for _ in range(60):
        if first.healthy:
            break
        time.sleep(0.5)
    for _ in range(a.nodes - 1):
        cluster.add()

    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(cluster))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"\nBộ cân bằng tải: http://127.0.0.1:{a.port}   ·   Demo trực tiếp: http://127.0.0.1:{a.port}/system/live")
    print("Lệnh: + thêm instance, - gỡ instance, s trạng thái, q thoát\n", flush=True)
    try:
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd == "+":
                cluster.add()
            elif cmd == "-":
                cluster.remove_last()
            elif cmd == "s":
                cluster.status()
            elif cmd in ("q", "quit", "exit"):
                break
            elif cmd:
                print("Lệnh: + - s q")
        else:
            # stdin bị đóng (chạy nền): giữ cụm chạy tới khi Ctrl+C
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[cluster] Dừng tất cả instance...")
        server.shutdown()
        cluster.stop_all()


if __name__ == "__main__":
    main()
