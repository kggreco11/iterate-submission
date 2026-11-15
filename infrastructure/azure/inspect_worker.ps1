$ErrorActionPreference = 'Continue'
Write-Output '=== Interactive sessions ==='
quser
Write-Output '=== Simulator worker tasks ==='
Get-ScheduledTask | Where-Object { $_.TaskName -match 'ChemSep.*Worker' } | Select-Object TaskName,State,@{N='User';E={$_.Principal.UserId}},@{N='LogonType';E={$_.Principal.LogonType}},@{N='Execute';E={$_.Actions.Execute}},@{N='Arguments';E={$_.Actions.Arguments}} | ConvertTo-Json -Depth 3
Write-Output '=== Worker health ==='
try { Invoke-RestMethod -Uri 'http://127.0.0.1:5701/health' -TimeoutSec 10 | ConvertTo-Json -Depth 5 } catch { Write-Output $_.Exception.Message }
Write-Output '=== Existing paths ==='
Get-Item 'C:\chemsep-benchmark\code','C:\iterate-hackathon' -ErrorAction SilentlyContinue | Select-Object FullName
