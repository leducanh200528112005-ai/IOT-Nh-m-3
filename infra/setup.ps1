$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function New-Password {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

if (-not (Test-Path '.env')) {
    @(
        'POSTGRES_DB=flood_monitor'
        'POSTGRES_USER=flood_admin'
        "POSTGRES_PASSWORD=$(New-Password)"
        "MQTT_DEVICE_PASSWORD=$(New-Password)"
        "MQTT_BACKEND_PASSWORD=$(New-Password)"
    ) | Set-Content -Path '.env' -Encoding ascii
    Write-Host 'Created .env with random passwords. Keep this file private.'
}

# Older .env files used MQTT_STATION_PASSWORD for the per-station account.
# Rename it so existing deployments keep the same device password.
$raw = Get-Content '.env'
if (($raw -match '^MQTT_STATION_PASSWORD=') -and -not ($raw -match '^MQTT_DEVICE_PASSWORD=')) {
    $raw = $raw | ForEach-Object {
        if ($_ -match '^MQTT_STATION_PASSWORD=(.*)$') { "MQTT_DEVICE_PASSWORD=$($matches[1])" } else { $_ }
    }
    $raw | Set-Content -Path '.env' -Encoding ascii
    Write-Host 'Renamed MQTT_STATION_PASSWORD to MQTT_DEVICE_PASSWORD in .env.'
}

$values = @{}
foreach ($line in Get-Content '.env') {
    if ($line -match '^([A-Z_]+)=(.*)$') {
        $values[$matches[1]] = $matches[2]
    }
}
foreach ($key in @('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'MQTT_DEVICE_PASSWORD', 'MQTT_BACKEND_PASSWORD')) {
    if (-not $values[$key] -or $values[$key] -match 'REPLACE_WITH') {
        throw "Missing or placeholder value for $key in .env"
    }
}

if (-not (Test-Path 'mosquitto/config/passwords')) {
    $oldDevice = $env:MQTT_DEVICE_PASSWORD
    $oldBackend = $env:MQTT_BACKEND_PASSWORD
    try {
        $env:MQTT_DEVICE_PASSWORD = $values['MQTT_DEVICE_PASSWORD']
        $env:MQTT_BACKEND_PASSWORD = $values['MQTT_BACKEND_PASSWORD']
        $configPath = Join-Path $PSScriptRoot 'mosquitto\config'
        # Only this temporary helper mounts config read/write.
        # Generate to a temporary file so a failure cannot leave a partial password file.
        docker run --rm --mount "type=bind,source=$configPath,target=/mosquitto/config" `
            -e MQTT_DEVICE_PASSWORD -e MQTT_BACKEND_PASSWORD `
            --entrypoint sh eclipse-mosquitto:2.0.22 -c `
            'set -eu; mosquitto_passwd -b -c /mosquitto/config/passwords.tmp station "$MQTT_DEVICE_PASSWORD"; mosquitto_passwd -b /mosquitto/config/passwords.tmp backend "$MQTT_BACKEND_PASSWORD"; chmod 644 /mosquitto/config/passwords.tmp; mv /mosquitto/config/passwords.tmp /mosquitto/config/passwords'
        if ($LASTEXITCODE -ne 0) { throw 'Could not generate MQTT password file.' }
    } finally {
        $env:MQTT_DEVICE_PASSWORD = $oldDevice
        $env:MQTT_BACKEND_PASSWORD = $oldBackend
    }
    Write-Host 'Created MQTT accounts: station (shared by all devices) and backend.'
} else {
    Write-Host 'Existing MQTT password file kept unchanged.'
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Invalid Compose configuration.' }
Write-Host 'Setup complete. Start services with: docker compose up -d'
