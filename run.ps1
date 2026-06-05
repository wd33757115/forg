# Use py launcher — Windows "python" may be the Store stub with no output.
& py -3 (Join-Path $PSScriptRoot "main.py") @args
exit $LASTEXITCODE
