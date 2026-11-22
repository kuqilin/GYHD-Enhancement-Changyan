# 在项目根目录执行： .\build.ps1
# 默认生成目录版（onedir，启动快、被杀毒误报少）；
# 加 -OneFile 则生成单文件 exe。

param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "安装 PyInstaller 失败" }

    $mode = if ($OneFile) { "--onefile" } else { "--onedir" }
    $pyArgs = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        $mode,
        "--name", "GYHD-Enhancement-Changyan",
        "--icon", "assets\GY_1080x1080.ico",
        "--add-data", "assets;assets",
        "--hidden-import", "win32com.client",
        "--hidden-import", "pythoncom",
        "--hidden-import", "pywintypes",
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
