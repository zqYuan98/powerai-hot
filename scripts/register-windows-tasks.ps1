[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot,
  [string]$CondaExecutable = "conda.exe",
  [string]$EnvironmentName = "ai-hot",
  [switch]$Unregister,
  [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if ($resolvedRoot.IndexOf('"') -ge 0 -or $CondaExecutable.IndexOf('"') -ge 0 -or $EnvironmentName.IndexOf('"') -ge 0) {
  throw "ProjectRoot, CondaExecutable, and EnvironmentName cannot contain double quotes."
}
$backend = Join-Path $resolvedRoot "backend"
if (-not (Test-Path -LiteralPath $backend -PathType Container)) { throw "Backend directory not found: $backend" }

$tasks = @(
  @{ Name = "E-AI-Ingest-News"; Schedule = @("/SC", "HOURLY", "/MO", "1"); Module = "jobs.ingest"; Arguments = "--group news" },
  @{ Name = "E-AI-Ingest-Papers"; Schedule = @("/SC", "DAILY", "/ST", "06:00"); Module = "jobs.ingest"; Arguments = "--group papers" },
  @{ Name = "E-AI-Daily-Digest"; Schedule = @("/SC", "DAILY", "/ST", "07:00"); Module = "jobs.digest"; Arguments = "" }
)

foreach ($task in $tasks) {
  if ($Unregister) {
    $command = "schtasks /Delete /TN `"$($task.Name)`" /F"
    if ($WhatIf) { Write-Output "WHATIF $command"; continue }
    & schtasks.exe /Delete /TN $task.Name /F 2>$null
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) { throw "Failed to remove task $($task.Name)" }
    continue
  }
  $action = "cmd.exe /d /s /c `"cd /d `"`"$backend`"`" && `"`"$CondaExecutable`"`" run -n `"`"$EnvironmentName`"`" python -m $($task.Module) $($task.Arguments)`""
  $command = "schtasks /Create /F /TN `"$($task.Name)`" $($task.Schedule -join ' ') /TR <action>"
  if ($WhatIf) { Write-Output "WHATIF $command"; Write-Output "ACTION $action"; continue }
  & schtasks.exe /Create /F /TN $task.Name @($task.Schedule) /TR $action | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Failed to create task $($task.Name)" }
}
