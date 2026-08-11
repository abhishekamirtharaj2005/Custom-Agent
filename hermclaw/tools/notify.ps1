Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = $args[0]
$n.BalloonTipText = $args[1]
$n.ShowBalloonTip(5000)
Start-Sleep -Seconds 3
$n.Dispose()
