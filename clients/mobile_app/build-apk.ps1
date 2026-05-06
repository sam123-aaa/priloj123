$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Join-Path $root "android_native"
$defaultToolRoot = "C:\Users\1\Documents\Codex\2026-05-06\d-pythonproject1\android-toolchain"

if (-not $env:JAVA_HOME) {
  $pyCharmJbr = "D:\paycharm1\PyCharm 2025.3.2.1\jbr"
  if (Test-Path (Join-Path $pyCharmJbr "bin\java.exe")) {
    $env:JAVA_HOME = $pyCharmJbr
  }
}

if (-not $env:ANDROID_SDK_ROOT) {
  $localSdk = Join-Path $defaultToolRoot "android-sdk"
  if (Test-Path (Join-Path $localSdk "platforms\android-35")) {
    $env:ANDROID_SDK_ROOT = $localSdk
    $env:ANDROID_HOME = $localSdk
  }
}

$gradle = Join-Path $defaultToolRoot "gradle-8.10.2\bin\gradle.bat"
if (-not (Test-Path $gradle)) {
  $gradle = "gradle"
}

$env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_SDK_ROOT\platform-tools;$env:Path"

Set-Location $project
& $gradle --no-daemon assembleDebug

$apk = Join-Path $project "app\build\outputs\apk\debug\app-debug.apk"
$out = Join-Path $root "MaintenanceMobile-debug.apk"
Copy-Item -LiteralPath $apk -Destination $out -Force
Write-Host "APK: $out"
