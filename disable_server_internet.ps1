$exePath = Join-Path -Path $PSScriptRoot -ChildPath "css_server\server\srcds.exe"

if (-Not (Test-Path $exePath)) {
    Write-Host "The specified file does not exist. Exiting script."
    exit
}

$sanitizedPath = $exePath -replace '[\\/:*?"<>|]', '_'
$inboundRuleName = "Block Inbound $sanitizedPath"
$outboundRuleName = "Block Outbound $sanitizedPath"

if (-not (Get-NetFirewallRule -DisplayName $inboundRuleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $inboundRuleName -Direction Inbound -Program $exePath -Action Block
}

if (-not (Get-NetFirewallRule -DisplayName $outboundRuleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $outboundRuleName -Direction Outbound -Program $exePath -Action Block
}
