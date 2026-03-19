# 文件上传到服务器脚本

param(
    [string]$SourcePath = "",
    [string]$TargetPath = "/home/lqj/liquid/",
    [switch]$Recursive = $false
)

# 服务器配置
$ServerHost = "liquid"  # 使用SSH配置的别名

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Upload-File {
    param([string]$Source, [string]$Target, [bool]$IsRecursive = $false)
    
    try {
        if ($IsRecursive) {
            Write-ColorOutput "上传目录: $Source -> ${ServerHost}:$Target" "Cyan"
            scp -r $Source "${ServerHost}:$Target"
        } else {
            Write-ColorOutput "上传文件: $Source -> ${ServerHost}:$Target" "Cyan"
            scp $Source "${ServerHost}:$Target"
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "上传成功" "Green"
            return $true
        } else {
            Write-ColorOutput "上传失败" "Red"
            return $false
        }
    } catch {
        Write-ColorOutput "上传错误: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Test-ServerConnection {
    Write-ColorOutput "测试服务器连接..." "Yellow"
    
    try {
        ssh $ServerHost "echo '连接成功'"
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "服务器连接正常" "Green"
            return $true
        } else {
            Write-ColorOutput "服务器连接失败" "Red"
            return $false
        }
    } catch {
        Write-ColorOutput "连接测试错误: $($_.Exception.Message)" "Red"
        return $false
    }
}

# 主程序
Write-ColorOutput "=" * 60 "Cyan"
Write-ColorOutput "文件上传到服务器工具" "Cyan"
Write-ColorOutput "=" * 60 "Cyan"

# 检查参数
if ([string]::IsNullOrEmpty($SourcePath)) {
    Write-ColorOutput "请指定源文件或目录路径" "Red"
    Write-ColorOutput "用法: .\upload_to_server.ps1 -SourcePath <路径> [-TargetPath <目标路径>] [-Recursive]" "Yellow"
    exit 1
}

# 检查源路径是否存在
if (-not (Test-Path $SourcePath)) {
    Write-ColorOutput "源路径不存在: $SourcePath" "Red"
    exit 1
}

# 测试服务器连接
if (-not (Test-ServerConnection)) {
    Write-ColorOutput "无法连接到服务器，请检查SSH配置" "Red"
    exit 1
}

# 确定是文件还是目录
$IsDirectory = Test-Path $SourcePath -PathType Container

if ($IsDirectory -and -not $Recursive) {
    Write-ColorOutput "检测到目录，是否递归上传？(y/n): " "Yellow" -NoNewline
    $response = Read-Host
    if ($response -eq 'y' -or $response -eq 'Y') {
        $Recursive = $true
    }
}

# 执行上传
Write-ColorOutput "开始上传..." "Yellow"
$success = Upload-File -Source $SourcePath -Target $TargetPath -IsRecursive $Recursive

if ($success) {
    Write-ColorOutput "文件上传完成" "Green"
    
    # 显示上传后的文件信息
    Write-ColorOutput "查看上传后的文件..." "Yellow"
    ssh $ServerHost "ls -la $TargetPath"
} else {
    Write-ColorOutput "文件上传失败" "Red"
    exit 1
}

Write-ColorOutput "=" * 60 "Cyan"