# ============================================================
#  TestHub Platform execution service bootstrap script
#  Purpose: ensure Redis (Celery broker) and Celery Worker are
#           running, so test case execution no longer fails
#           with "timeout of 30000ms exceeded" / pending tasks.
#  Usage  : right-click -> "Run with PowerShell", or register
#           with Task Scheduler for auto-start on boot.
#  Note   : idempotent, safe to run repeatedly.
# ============================================================

$ProjectRoot = "C:\Users\86150\Doubao\chats\2026-09-15\new-chat-1\testhub_platform-main"
$LogDir = "$ProjectRoot\logs"
$RedisPassword = "1234"   # must match REDIS_URL password in project .env

Write-Host "========================================"
Write-Host " TestHub execution service bootstrap"
Write-Host "========================================"

# ---------- 1. ensure Redis container is running ----------
Write-Host "[1/2] Checking Redis container - 127.0.0.1:6379 ..."
$container = docker ps -a --filter "name=^/testhub-redis$" --format "{{.Names}}" 2>$null
if ($container -eq "testhub-redis") {
    $state = docker inspect -f "{{.State.Running}}" testhub-redis 2>$null
    if ($state -eq "true") {
        Write-Host "  Redis already running OK"
    }
    else {
        docker start testhub-redis | Out-Null
        Write-Host "  Redis container started OK"
    }
}
else {
    docker run -d --name testhub-redis -p 6379:6379 redis:7-alpine redis-server --requirepass $RedisPassword | Out-Null
    Write-Host "  Redis container created and started OK"
}

# verify port 6379 is reachable
$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $tcp.Connect("127.0.0.1", 6379)
    Write-Host "  Port 6379 reachable OK"
    $tcp.Close()
}
catch {
    Write-Host "  WARNING: port 6379 not reachable yet, Redis may still be starting"
}

# ---------- 2. ensure Celery worker is running ----------
Write-Host "[2/2] Checking Celery Worker ..."
$celeryProc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @('python.exe', 'celery.exe') -and $_.CommandLine -match 'celery' -and $_.CommandLine -match 'backend' }
if ($celeryProc) {
    Write-Host "  Celery Worker already running (PID: $($celeryProc.ProcessId)) OK"
}
else {
    $workerOut = "$LogDir\celery_worker.out.log"
    $workerErr = "$LogDir\celery_worker.err.log"
    Start-Process -FilePath "$ProjectRoot\venv\Scripts\celery.exe" `
        -ArgumentList '-A', 'backend', 'worker', '-l', 'info', '-P', 'solo' `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $workerOut `
        -RedirectStandardError $workerErr `
        -WindowStyle Hidden
    Write-Host "  Celery Worker started OK (logs: logs\celery_worker.out.log / .err.log)"
}

Write-Host ""
Write-Host "All ready. You can run test cases now."
