# Forge 常用 Demo 脚本（Windows PowerShell）
# 5 分钟讲稿见 docs/DEMO_SCRIPT.md
param(
    [ValidateSet("security", "itil", "mixed", "general")]
    [string]$Type = "security",
    [switch]$AutoApprove,
    [switch]$Report,
    [switch]$Plain
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
$Args = @("main.py", "--type", $Type, "--no-feedback", "--no-report-prompt")
if ($AutoApprove) { $Args += "--auto-approve" }
if ($Report) { $Args += "--report" }
if ($Plain) { $Args += "--plain" }

& $Py @Args
