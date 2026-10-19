# Build "Communication Aid.exe" and a Windows installer (Setup.exe) to copy to other PCs.
#
#   conda activate commu-aid
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
#   ... -NoTranslate        much smaller; Speak says the English instead of Thai
#   ... -Version 0.2.0
#
# Output: dist\CommunicationAid-<version>-Windows-Setup.exe (needs Inno Setup 6; without it,
# dist\CommunicationAid-<version>-Windows.zip of the app folder instead).
# The Tobii Pro Spark runtime is NOT included: install it on each PC from Tobii Connect
# (README, "Install on Windows").
param(
    [switch]$NoTranslate,
    [string]$Version = "0.1.0"
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

$AppName = "Communication Aid"
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

& $Python -c "import sys; sys.exit(sys.version_info[:2] != (3, 10))"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Needs Python 3.10 (tobii-research only works there). Run: conda activate commu-aid"
}
$Modules = @("PySide6", "yaml", "tobii_research", "win32com.client")
if (-not $NoTranslate) { $Modules += @("torch", "transformers", "sentencepiece") }
foreach ($Module in $Modules) {
    & $Python -c "import $Module" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python module '$Module' is missing. Run: pip install -r requirements.txt -r requirements-tobii.txt -r requirements-translate.txt"
    }
}

Write-Host "==> Installing PyInstaller"
& $Python -m pip install --quiet -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed" }

$Translate = if ($NoTranslate) { "0" } else { "1" }
Write-Host "==> Building $AppName.exe (version $Version, translation $(if ($NoTranslate) { 'off' } else { 'on' }))"
if (Test-Path "dist\$AppName") { Remove-Item -Recurse -Force "dist\$AppName" }
$env:COMMU_AID_TRANSLATE = $Translate
& $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\windows\commu_aid.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed" }

$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    foreach ($Dir in @("${env:ProgramFiles(x86)}\Inno Setup 6", "$env:ProgramFiles\Inno Setup 6", "$env:LOCALAPPDATA\Programs\Inno Setup 6")) {
        if (Test-Path "$Dir\ISCC.exe") { $Iscc = "$Dir\ISCC.exe"; break }
    }
}
if ($Iscc) {
    Write-Host "==> Making the installer with Inno Setup"
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$Root\dist\$AppName" "/DOutputDir=$Root\dist" packaging\windows\installer.iss
    if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup failed" }
    $Out = "dist\CommunicationAid-$Version-Windows-Setup.exe"
} else {
    Write-Host "==> Inno Setup 6 not found (https://jrsoftware.org/isdl.php); making a zip instead"
    Copy-Item "packaging\windows\Read Me First.txt" "dist\$AppName\"
    $Out = "dist\CommunicationAid-$Version-Windows.zip"
    if (Test-Path $Out) { Remove-Item $Out }
    Compress-Archive -Path "dist\$AppName" -DestinationPath $Out
}

Write-Host ""
Write-Host "Done: $Out ($([math]::Round((Get-Item $Out).Length / 1MB)) MB)"
Write-Host "Copy it to the other PC and follow 'Install on Windows' in the README (short version: Read Me First.txt)."
