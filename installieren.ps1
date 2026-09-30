# Nasdaq-Grid auf einem PC einrichten: legt C:\Nasdaq-Grid an und laedt alle Dateien aus dem Repo.
# Aufruf in PowerShell:  irm https://raw.githubusercontent.com/finntraidingview-cmd/nasdaq-grid/main/installieren.ps1 | iex
$ziel = 'C:\Nasdaq-Grid'
$b = 'https://raw.githubusercontent.com/finntraidingview-cmd/nasdaq-grid/main/'
New-Item -ItemType Directory -Force -Path $ziel | Out-Null
foreach ($f in @('grid.py','update.py','selftest.py','einrichten.py','einrichten.bat','dashboard.py','dashboard.html','start-dashboard.bat','VERSION','start-long.bat','start-short.bat','config-long.vorlage.json','config-short.vorlage.json','README.md')) {
  Invoke-RestMethod ($b + $f) -OutFile (Join-Path $ziel $f)
}
python -c "import MetaTrader5" 2>$null
if ($LASTEXITCODE -ne 0) { python -m pip install MetaTrader5 }
Write-Host "Fertig: $ziel  - jetzt einrichten.bat starten, danach start-long.bat, start-short.bat und start-dashboard.bat."
