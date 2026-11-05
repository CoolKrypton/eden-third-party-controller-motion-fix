# Watchdog: kill cc1plus processes that stop making CPU progress (MSYS2 fork/exec deadlock).
# Logs to F:\MyCodes\c++\eden\build-mingw-pgo-watchdog.log
$log = "F:\MyCodes\c++\eden\build-mingw-pgo-watchdog.log"
$hist = @{}
while ($true) {
    Start-Sleep -Seconds 20
    try {
        $procs = Get-Process cc1plus -ErrorAction SilentlyContinue
        if (-not $procs) { continue }
        foreach ($p in $procs) {
            try {
                $cpu = $p.TotalProcessorTime.TotalSeconds
                $age = ((Get-Date) - $p.StartTime).TotalSeconds
                if ($age -lt 90) { continue }
                if (-not $hist.ContainsKey($p.Id)) {
                    $hist[$p.Id] = @{ cpu = $cpu; strikes = 0 }
                    continue
                }
                $h = $hist[$p.Id]
                if ([math]::Abs($cpu - $h.cpu) -lt 0.8) {
                    $h.strikes++
                } else {
                    $h.strikes = 0
                    $h.cpu = $cpu
                }
                if ($h.strikes -ge 4) {
                    "{0} KILL pid={1} stuck at {2:N1}s cpu, age {3:N0}s" -f (Get-Date -Format 'HH:mm:ss'), $p.Id, $cpu, $age | Out-File -Append -Encoding utf8 $log
                    try { $p.Kill(); $hist.Remove($p.Id) } catch { }
                }
            } catch { }
        }
        # drop entries for exited processes
        $alive = $procs.Id
        foreach ($k in @($hist.Keys)) { if ($alive -notcontains $k) { $hist.Remove($k) } }
    } catch { }
}
