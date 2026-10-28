<#
.SYNOPSIS
  Stop the MedAI backend (port 8000) and frontend (port 5173) started by scripts\start.ps1.
  Only python/node processes are stopped, so an unrelated program using these ports is left alone.
#>
$expected = @{ 8000 = @('python', 'pythonw', 'uvicorn'); 5173 = @('node') }
foreach ($port in $expected.Keys) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "Nothing is listening on port $port."; continue }
    foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        if ($expected[$port] -notcontains $proc.ProcessName.ToLower()) {
            Write-Warning "Port $port is used by '$($proc.ProcessName)' (PID $procId), which is not MedAI. Leaving it running."
            continue
        }
        Write-Host "Stopping $($proc.ProcessName) (PID $procId) on port $port"
        # /T also stops child processes (uvicorn reloader workers, node/vite)
        taskkill /PID $procId /T /F | Out-Null
    }
}
Write-Host 'Done. You can also close the "MedAI backend" and "MedAI frontend" windows.'
