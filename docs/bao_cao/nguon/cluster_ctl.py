"""Chạy local_cluster.py, đọc lệnh (+, -, s, q) từ file cmd.txt."""
import subprocess, sys, time, os
root, cmdfile = sys.argv[1], sys.argv[2]
open(cmdfile, "w").close()
p = subprocess.Popen([os.path.join(root, r"py_cloudshop\Scripts\python.exe"), "-u", r"scripts\local_cluster.py", "--nodes", "2"],
                     cwd=root, stdin=subprocess.PIPE, text=True)
seen = 0
while p.poll() is None:
    lines = open(cmdfile).read().splitlines()
    for c in lines[seen:]:
        p.stdin.write(c + "\n"); p.stdin.flush()
    seen = len(lines)
    time.sleep(0.5)
