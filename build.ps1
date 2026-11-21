# 在项目根目录执行： .\build.ps1
# 生成单文件 exe；加 -OneDir 则生成目录版（启动更快、误报更少）。

param(
    [switch]$OneDir
)

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "安装 PyInstaller 失败" }

    $mode = if ($OneDir) { "--onedir" } else { "--onefile" }
    $pyArgs = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        $mode,
        "--name", "GYHD-Enhancement-Changyan",
        "--icon", "assets\GY_1080x1080.ico",
        "--add-data", "assets;assets",
        "--hidden-import", "win32com.client",
        "main.py"
    )
    python -m PyInstaller @pyArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

    Write-Host ""
    Write-Host "打包完成：" -ForegroundColor Green
    Get-ChildItem dist | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
}
finally {
    Pop-Location
}
