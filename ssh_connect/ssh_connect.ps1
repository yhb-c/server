# SSH Connect Script for Liquid Detection System
# Configure passwordless SSH connection to server
#使用 ssh liquid 直接连接服务器，无需输入密码
#使用 ssh liquid "command" 执行远程命令
#使用 scp 进行文件传输scp local_file.txt liquid:/home/lqj/liquid/


# Global Variables
$SERVER_HOST = "192.168.0.121"
$SERVER_USER = "lqj"
$SSH_CONFIG_HOST = "liquid"
$LOCAL_SSH_DIR = "$env:USERPROFILE\.ssh"
$PRIVATE_KEY_PATH = "$LOCAL_SSH_DIR\liquid_server_key"
$PUBLIC_KEY_PATH = "$LOCAL_SSH_DIR\liquid_server_key.pub"
$SSH_CONFIG_PATH = "$LOCAL_SSH_DIR\config"

function Write-LogMessage {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = "White"
    if ($Level -eq "ERROR") { $color = "Red" }
    elseif ($Level -eq "WARN") { $color = "Yellow" }
    elseif ($Level -eq "SUCCESS") { $color = "Green" }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-CommandExists {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Test-NetworkConnection {
    param([string]$HostIP, [int]$Count = 4)
    Write-LogMessage "Testing network connection to $HostIP..."
    
    try {
        # Use ping command to get detailed output with TTL
        Write-LogMessage "Executing ping command with detailed output..."
        $pingOutput = & ping -n $Count $HostIP 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "Network connection to $HostIP is successful" "SUCCESS"
            
            # Display detailed ping output
            foreach ($line in $pingOutput) {
                if ($line -match "来自|Reply from|TTL|时间|time") {
                    Write-LogMessage "  $line" "INFO"
                }
            }
            
            # Extract and display statistics
            $statsLines = $pingOutput | Where-Object { $_ -match "数据包|Packets|最短|Minimum|最长|Maximum|平均|Average" }
            foreach ($statsLine in $statsLines) {
                Write-LogMessage "  $statsLine" "INFO"
            }
            
            return $true
        } else {
            Write-LogMessage "Network connection to $HostIP failed" "ERROR"
            Write-LogMessage "Ping output:" "ERROR"
            foreach ($line in $pingOutput) {
                Write-LogMessage "  $line" "ERROR"
            }
            Write-LogMessage "Please check network connectivity and server status" "ERROR"
            return $false
        }
    }
    catch {
        Write-LogMessage "Network test error: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

# Test network connection first
if (-not (Test-NetworkConnection $SERVER_HOST)) {
    Write-LogMessage "Cannot reach server $SERVER_HOST, aborting SSH configuration" "ERROR"
    exit 1
}

# Check required commands
Write-LogMessage "Checking required commands..."
$requiredCommands = @("ssh", "ssh-keygen", "scp")
foreach ($cmd in $requiredCommands) {
    if (-not (Test-CommandExists $cmd)) {
        Write-LogMessage "Missing required command: $cmd" "ERROR"
        Write-LogMessage "Please install OpenSSH client" "ERROR"
        exit 1
    }
}

# Create SSH directory
Write-LogMessage "Creating SSH directory..."
if (-not (Test-Path $LOCAL_SSH_DIR)) {
    New-Item -ItemType Directory -Path $LOCAL_SSH_DIR -Force | Out-Null
    Write-LogMessage "SSH directory created successfully" "SUCCESS"
} else {
    Write-LogMessage "SSH directory already exists"
}

# Generate SSH key pair
Write-LogMessage "Generating SSH key pair..."
if (Test-Path $PRIVATE_KEY_PATH) {
    Write-LogMessage "SSH key already exists" "WARN"
    $overwrite = Read-Host "Overwrite existing key? (y/N)"
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-LogMessage "Skipping key generation"
    } else {
        & ssh-keygen -t rsa -b 4096 -f $PRIVATE_KEY_PATH -N '""' -C "liquid_client"
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "SSH key pair generated successfully" "SUCCESS"
        } else {
            Write-LogMessage "Failed to generate SSH key pair" "ERROR"
            exit 1
        }
    }
} else {
    & ssh-keygen -t rsa -b 4096 -f $PRIVATE_KEY_PATH -N '""' -C "liquid_client"
    if ($LASTEXITCODE -eq 0) {
        Write-LogMessage "SSH key pair generated successfully" "SUCCESS"
    } else {
        Write-LogMessage "Failed to generate SSH key pair" "ERROR"
        exit 1
    }
}

# Copy public key to server
Write-LogMessage "Copying public key to server (please enter server password)..."
& scp -o StrictHostKeyChecking=no $PUBLIC_KEY_PATH "${SERVER_USER}@${SERVER_HOST}:~/.ssh/authorized_keys_temp"
if ($LASTEXITCODE -eq 0) {
    Write-LogMessage "Public key copied successfully" "SUCCESS"
    
    # Configure authorized_keys on server
    Write-LogMessage "Configuring authorized_keys on server..."
    $sshCommand = "mkdir -p ~/.ssh; cat ~/.ssh/authorized_keys_temp >> ~/.ssh/authorized_keys; rm ~/.ssh/authorized_keys_temp; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
    & ssh -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_HOST}" $sshCommand
    
    if ($LASTEXITCODE -eq 0) {
        Write-LogMessage "Server configuration completed successfully" "SUCCESS"
    } else {
        Write-LogMessage "Failed to configure server" "ERROR"
        exit 1
    }
} else {
    Write-LogMessage "Failed to copy public key to server" "ERROR"
    exit 1
}

# Update SSH config
Write-LogMessage "Updating SSH config..."
$configContent = @"
Host $SSH_CONFIG_HOST
    HostName $SERVER_HOST
    User $SERVER_USER
    IdentityFile $PRIVATE_KEY_PATH
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ServerAliveInterval 60
    ServerAliveCountMax 3

"@

if (Test-Path $SSH_CONFIG_PATH) {
    Add-Content $SSH_CONFIG_PATH $configContent
} else {
    Set-Content $SSH_CONFIG_PATH $configContent
}
Write-LogMessage "SSH config updated successfully" "SUCCESS"

# Test SSH connection
Write-LogMessage "Testing SSH connection..."
$testResult = & ssh -o ConnectTimeout=10 -o BatchMode=yes $SSH_CONFIG_HOST "echo 'Connection test successful'"
if ($LASTEXITCODE -eq 0) {
    Write-LogMessage "SSH passwordless connection test successful: $testResult" "SUCCESS"
    Write-LogMessage "Configuration completed! You can now use: ssh $SSH_CONFIG_HOST" "SUCCESS"
} else {
    Write-LogMessage "SSH connection test failed" "ERROR"
    Write-LogMessage "Please check the configuration manually" "WARN"
}