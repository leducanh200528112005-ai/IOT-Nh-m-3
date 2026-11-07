$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.env')) {
    $infra = @{}
    foreach ($line in Get-Content '..\infra\.env') {
        if ($line -match '^([A-Z_]+)=(.*)$') { $infra[$matches[1]] = $matches[2] }
    }
    foreach ($key in @('POSTGRES_PASSWORD', 'MQTT_BACKEND_PASSWORD')) {
        if (-not $infra[$key]) { throw "Missing $key in infra/.env" }
    }
    @(
        'DB_HOST=localhost', 'DB_PORT=5432'
        "DB_NAME=$($infra['POSTGRES_DB'])", "DB_USER=$($infra['POSTGRES_USER'])"
        "DB_PASSWORD=$($infra['POSTGRES_PASSWORD'])"
        'MQTT_HOST=localhost', 'MQTT_PORT=1883', 'MQTT_USERNAME=backend'
        "MQTT_PASSWORD=$($infra['MQTT_BACKEND_PASSWORD'])"
        'MQTT_ENABLED=true', 'MQTT_CLIENT_ID=flood-backend'
        'DATA_STALE_SECONDS=15', 'CORS_ORIGINS=["http://localhost:5173"]'
    ) | Set-Content '.env' -Encoding ascii
    Write-Host 'Created backend/.env from existing infrastructure credentials.'
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 first.' }
}
& .\.venv\Scripts\python.exe -m pip install -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Next: .\.venv\Scripts\python.exe -m alembic upgrade head'
