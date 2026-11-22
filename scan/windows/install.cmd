@echo off
rem builds PRISMO scan with the C# compiler that comes with Windows and starts it (also at login).
rem   install.cmd            (asks for the scan key the first time)
rem   install.cmd uninstall
setlocal
set "OUT=%LOCALAPPDATA%\PrismoScan"
set "CFG=%APPDATA%\prismo-scan"
taskkill /im PrismoScan.exe /f >nul 2>&1

if /i "%~1"=="uninstall" (
  reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v PrismoScan /f >nul 2>&1
  rmdir /s /q "%OUT%" 2>nul
  echo PRISMO scan removed
  exit /b 0
)

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo no csc.exe found, turn on .NET Framework 4.8 in "Windows-Features aktivieren"
  pause
  exit /b 1
)

if not exist "%OUT%" mkdir "%OUT%"
if not exist "%CFG%" mkdir "%CFG%"
echo ==^> building
"%CSC%" /nologo /target:winexe /optimize /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll /out:"%OUT%\PrismoScan.exe" "%~dp0PrismoScan.cs"
if errorlevel 1 (
  echo build failed
  pause
  exit /b 1
)

if exist "%CFG%\key" goto start
set /p "KEY=scan key (install-pi.sh printed it): "
> "%CFG%\key" echo %KEY%

:start
start "" "%OUT%\PrismoScan.exe"
echo PRISMO scan is running (QR icon in the tray, maybe behind the ^^ arrow)
