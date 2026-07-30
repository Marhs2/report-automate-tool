"""실행 중인 run_benchmark.py 프로세스를 찾아 종료한다."""

import subprocess

raw = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:list"],
    capture_output=True, shell=True,
).stdout.decode("cp949", errors="replace")

targets = []
for block in raw.split("\n\n"):
    cmd = pid = None
    for line in block.splitlines():
        if line.startswith("CommandLine="):
            cmd = line[len("CommandLine="):]
        elif line.startswith("ProcessId="):
            pid = line[len("ProcessId="):].strip()
    if cmd and pid and "run_benchmark.py" in cmd:
        targets.append((pid, cmd[:140]))

if not targets:
    print("run_benchmark.py 실행 중 아님")
for pid, cmd in targets:
    r = subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, shell=True)
    print(f"kill {pid} rc={r.returncode} :: {cmd}")
