param(
    [string]$EntryPoint = "XMLDiffStudio.py",
    [string]$AppName = "XMLDiffStudio",
    [string]$IconPath = ".\\assets\\xmldiffstudio-icon.ico"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "No se encontro .venv. Crea el entorno virtual e instala dependencias antes de compilar."
}

.\.venv\Scripts\python.exe -m pip install pyinstaller

$iconArgs = @()
if (Test-Path $IconPath) {
    $iconArgs = @("--icon", $IconPath)
}

$dataArgs = @()
if (Test-Path ".\\assets\\xmldiffstudio-icon.png") {
    $dataArgs += @("--add-data", ".\\assets\\xmldiffstudio-icon.png;assets")
}
if (Test-Path ".\\assets\\xmldiffstudio-icon.ico") {
    $dataArgs += @("--add-data", ".\\assets\\xmldiffstudio-icon.ico;assets")
}

.\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $AppName `
    @iconArgs `
    @dataArgs `
    $EntryPoint

Write-Host "Build listo en .\dist\$AppName\$AppName.exe"
