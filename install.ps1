# ============================================================
#   ARASAKA TECHIE // instalador Windows
#   Uso:  clique duas vezes em install.bat
#         (ou: powershell -ExecutionPolicy Bypass -File install.ps1)
# ============================================================
$ErrorActionPreference = 'Stop'
$App  = 'arasaka-techie'
$Dir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Data = Join-Path $env:LOCALAPPDATA $App
$Bin  = Join-Path $Data 'bin'

function Step($t) { Write-Host ""; Write-Host "[$script:n] $t" -ForegroundColor Red; $script:n++ }
function Ok($t)   { Write-Host "     ■ $t" -ForegroundColor Gray }
function Warn($t) { Write-Host "     !! $t" -ForegroundColor Yellow }
$script:n = 1

Write-Host ""
Write-Host "   A R A S A K A   T E C H I E" -ForegroundColor Red
Write-Host "   Simulador de montagem de PC" -ForegroundColor DarkGray

if (-not (Test-Path (Join-Path $Dir 'arasaka_techie\app.py'))) { throw "Arquivos do app nao encontrados em $Dir" }

Step "Python"
$py = $null
foreach ($c in @('py', 'python', 'python3')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $py = $cmd.Source; break }
}
if (-not $py) {
    Warn "Python nao encontrado. Instalando com winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $py = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $py) { throw "Instale o Python 3.9+ (python.org) e rode de novo." }
}
$ver = & $py -c "import sys; print('%d.%d' % sys.version_info[:2])"
Ok "Python $ver ($py)"

Step "Ambiente Python (PySide6 / Qt 6)"
New-Item -ItemType Directory -Force -Path $Data, $Bin | Out-Null
$vpy = Join-Path $Data 'venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { & $py -m venv (Join-Path $Data 'venv') }
& $vpy -m pip install -q --upgrade pip 2>$null | Out-Null
Write-Host "     › baixando PySide6 (~120 MB na primeira vez)..."
& $vpy -m pip install -q --upgrade "PySide6-Essentials>=6.5"
if ($LASTEXITCODE -ne 0) { throw "falha ao instalar as dependencias do Python" }
Ok ("PySide6 " + (& $vpy -c "import PySide6; print(PySide6.__version__)"))

Step "Arquivos do app"
$appDir = Join-Path $Data 'app'
if (Test-Path $appDir) { Remove-Item -Recurse -Force $appDir }
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item -Recurse (Join-Path $Dir 'arasaka_techie') $appDir
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $appDir | Remove-Item -Recurse -Force
$pyw = Join-Path $Data 'venv\Scripts\pythonw.exe'
# lancador: roda "python -m arasaka_techie" sem janela de console, de qualquer diretorio
$launch = Join-Path $Data 'launch.pyw'
Set-Content -Encoding UTF8 -Path $launch -Value @"
import runpy, sys
sys.path.insert(0, r"$appDir")
sys.argv[0] = "arasaka_techie"
runpy.run_module("arasaka_techie", run_name="__main__", alter_sys=True)
"@
Set-Content -Encoding ASCII -Path (Join-Path $Bin "$App.cmd") -Value "@echo off`r`nstart `"`" `"$pyw`" `"$launch`" %*"

# icone .ico gerado a partir do SVG
$ico = Join-Path $Data "$App.ico"
$svg = Join-Path $appDir 'arasaka_techie\assets\arasaka-techie.svg'
if (Test-Path $svg) {
    & $vpy -c "import sys; from PySide6.QtGui import QGuiApplication, QIcon; a=QGuiApplication(sys.argv); QIcon(sys.argv[1]).pixmap(256,256).save(sys.argv[2])" $svg $ico 2>$null
}

# PATH do usuario
$up = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not ($up -split ';' | Where-Object { $_ -eq $Bin })) {
    [Environment]::SetEnvironmentVariable('Path', ($up.TrimEnd(';') + ';' + $Bin), 'User')
    Ok "comando 'arasaka-techie' adicionado ao PATH (abra um novo terminal)"
}

# atalhos
$ws = New-Object -ComObject WScript.Shell
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Arasaka Techie.lnk'
$desk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Arasaka Techie.lnk'
foreach ($lnk in @($menu, $desk)) {
    $s = $ws.CreateShortcut($lnk)
    $s.TargetPath = $pyw
    $s.Arguments = "`"$launch`""
    $s.WorkingDirectory = $env:USERPROFILE
    if (Test-Path $ico) { $s.IconLocation = $ico }
    $s.Description = 'Arasaka Techie - Simulador de montagem de PC'
    $s.Save()
}
Ok "atalhos no Menu Iniciar e na Area de Trabalho"

Write-Host ""
Write-Host " ■ INSTALACAO CONCLUIDA" -ForegroundColor Red
Write-Host "   Abra 'Arasaka Techie' no Menu Iniciar."
Write-Host ""
