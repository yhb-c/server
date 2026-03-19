# PowerShell脚本：上传修复后的文件到服务器

Write-Host "上传HKcapture修复文件到服务器" -ForegroundColor Green
Write-Host "=" * 50

# 服务器配置
$serverIP = "192.168.0.121"
$username = "lqj"
$password = "admin"

# 要上传的文件
$filesToUpload = @(
    @{
        Local = "server\video\video_capture_factory.py"
        Remote = "/home/lqj/liquid/server/video/video_capture_factory.py"
    },
    @{
        Local = "test\simple_hkcapture_test.py"
        Remote = "/home/lqj/liquid/test/simple_hkcapture_test.py"
    }
)

# 检查文件是否存在并上传
$successCount = 0
foreach ($file in $filesToUpload) {
    if (Test-Path $file.Local) {
        Write-Host "上传: $($file.Local) -> $($file.Remote)" -ForegroundColor Yellow
        
        # 使用pscp上传文件（如果可用）
        try {
            $pscpCmd = "echo $password | pscp -pw $password -o StrictHostKeyChecking=no $($file.Local) ${username}@${serverIP}:$($file.Remote)"
            Invoke-Expression $pscpCmd
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  上传成功" -ForegroundColor Green
                $successCount++
            } else {
                Write-Host "  上传失败" -ForegroundColor Red
            }
        } catch {
            Write-Host "  pscp不可用，尝试scp..." -ForegroundColor Yellow
            
            # 尝试使用scp
            try {
                $scpCmd = "scp -o StrictHostKeyChecking=no $($file.Local) ${username}@${serverIP}:$($file.Remote)"
                Start-Process -FilePath "scp" -ArgumentList "-o", "StrictHostKeyChecking=no", $file.Local, "${username}@${serverIP}:$($file.Remote)" -Wait
                
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  上传成功" -ForegroundColor Green
                    $successCount++
                } else {
                    Write-Host "  上传失败" -ForegroundColor Red
                }
            } catch {
                Write-Host "  scp也不可用，请手动上传文件" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "本地文件不存在: $($file.Local)" -ForegroundColor Red
    }
}

Write-Host "`n上传完成: $successCount/$($filesToUpload.Count)" -ForegroundColor Cyan

if ($successCount -eq $filesToUpload.Count) {
    Write-Host "`n运行远程测试..." -ForegroundColor Green
    
    # 运行远程测试
    try {
        $testCmd = "ssh -o StrictHostKeyChecking=no ${username}@${serverIP} 'cd /home/lqj/liquid && source ~/anaconda3/bin/activate liquid && python test/simple_hkcapture_test.py'"
        $testResult = Invoke-Expression $testCmd
        
        Write-Host "测试输出:" -ForegroundColor Yellow
        Write-Host $testResult
        
        if ($testResult -match "所有测试通过") {
            Write-Host "`n测试成功！HKcapture导入修复完成" -ForegroundColor Green
        } else {
            Write-Host "`n测试失败，需要进一步调试" -ForegroundColor Red
        }
    } catch {
        Write-Host "远程测试失败: $_" -ForegroundColor Red
    }
} else {
    Write-Host "文件上传不完整，跳过测试" -ForegroundColor Red
}

Write-Host "`n请手动使用以下命令上传文件（如果自动上传失败）:" -ForegroundColor Yellow
Write-Host "scp server/video/video_capture_factory.py lqj@192.168.0.121:/home/lqj/liquid/server/video/"
Write-Host "scp test/simple_hkcapture_test.py lqj@192.168.0.121:/home/lqj/liquid/test/"
Write-Host "`n然后在服务器上运行测试:"
Write-Host "ssh lqj@192.168.0.121"
Write-Host "cd /home/lqj/liquid"
Write-Host "source ~/anaconda3/bin/activate liquid"
Write-Host "python test/simple_hkcapture_test.py"