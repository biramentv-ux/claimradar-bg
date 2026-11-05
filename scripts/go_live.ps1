# ClaimRadar BG - пускане на живо в Hugging Face Space (Windows PowerShell 5.1+ / PowerShell 7)
#
# Еднократно пускане:
#   irm https://raw.githubusercontent.com/biramentv-ux/claimradar-bg/main/scripts/go_live.ps1 | iex
#
# Какво прави:
#   1. Пита за Hugging Face token (write) - не се записва никъде.
#   2. Задава Space Variables (PUBLIC_BASE_URL и др.) - към custom домейна, ако
#      DNS-ът вече сочи към hf.space, иначе към *.hf.space адреса.
#   3. По желание генерира нови OWNER/ADMIN ключове и salt-ове като Secrets и ги
#      записва във файл на работния плот (само за теб).
#   4. По желание задава OPENAI_API_KEY и DATABASE_URL като Secrets.
#   5. Сваля паузата и рестартира Space-а, изчаква RUNNING и проверява /health и /.

& {
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$SpaceId      = 'DyrakArmy/claimradar-bg'
$HfSpaceUrl   = 'https://dyrakarmy-claimradar-bg.hf.space'
$CustomDomain = 'claimradar.dyrakarmy.eu'
$RootDomain   = 'dyrakarmy.eu'
$Api          = "https://huggingface.co/api/spaces/$SpaceId"

function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }

function Read-Secret($prompt) {
    $secure = Read-Host -Prompt $prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function New-RandomKey([int]$bytes = 32) {
    $buf = New-Object byte[] $bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buf); $rng.Dispose()
    return ([Convert]::ToBase64String($buf)).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Invoke-Hf($method, $path, $body = $null) {
    $params = @{ Method = $method; Uri = "$Api$path"; Headers = $Headers }
    if ($null -ne $body) {
        $params.Body = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Compress))
        $params.ContentType = 'application/json; charset=utf-8'
    }
    return Invoke-RestMethod @params
}

function Set-SpaceVariable($key, $value) {
    Invoke-Hf 'POST' '/variables' @{ key = $key; value = $value } | Out-Null
    Say "  variable $key = $value" 'DarkGray'
}

function Set-SpaceSecret($key, $value) {
    Invoke-Hf 'POST' '/secrets' @{ key = $key; value = $value } | Out-Null
    Say "  secret   $key = ****" 'DarkGray'
}

Say "`n=== ClaimRadar BG -> публично пускане ===`n" 'Cyan'

# 1. Token
Say 'Трябва ти Hugging Face token с WRITE права: https://huggingface.co/settings/tokens'
$token = Read-Secret 'HF token'
if ([string]::IsNullOrWhiteSpace($token)) { throw 'Няма въведен token.' }
$Headers = @{ Authorization = "Bearer $($token.Trim())" }

try {
    $runtime = Invoke-Hf 'GET' '/runtime'
} catch {
    throw "Token-ът няма достъп до $SpaceId (проверка: write права и собственост на Space-а). $($_.Exception.Message)"
}
Say "Текущ статус на Space-а: $($runtime.stage)" 'Yellow'

# 2. Домейн: ползваме custom домейна само ако DNS вече сочи към hf.space
$domainReady = $false
try {
    $dns = Resolve-DnsName -Name $CustomDomain -Type CNAME -ErrorAction Stop |
        Where-Object { $_.Type -eq 'CNAME' } | Select-Object -First 1
    if ($dns -and $dns.NameHost -match 'hf\.space\.?$') { $domainReady = $true }
} catch {}

if ($domainReady) {
    $publicUrl = "https://$CustomDomain"
    Say "DNS: $CustomDomain -> hf.space (OK)" 'Green'
} else {
    $publicUrl = $HfSpaceUrl
    Say "DNS: $CustomDomain още не сочи към hf.space -> временно ползвам $HfSpaceUrl" 'Yellow'
}

Say "`nЗадавам Variables..." 'Cyan'
Set-SpaceVariable 'PUBLIC_BASE_URL' $publicUrl
Set-SpaceVariable 'CUSTOM_DOMAIN'   $CustomDomain
Set-SpaceVariable 'ROOT_DOMAIN'     $RootDomain
Set-SpaceVariable 'HF_SPACE_URL'    $HfSpaceUrl

# 3. Admin ключове и salt-ове
$answer = Read-Host "`nДа генерирам ли НОВИ OWNER/ADMIN ключове и salt-ове? Старите ще бъдат заменени. [Y/n]"
if ($answer -notmatch '^(n|no|н|не)$') {
    $keys = [ordered]@{
        OWNER_KEY            = New-RandomKey
        ADMIN_KEY            = New-RandomKey
        AUTH_TOKEN_SALT      = New-RandomKey 48
        RATE_LIMIT_HASH_SALT = New-RandomKey 48
    }
    Say 'Задавам Secrets...' 'Cyan'
    foreach ($k in $keys.Keys) { Set-SpaceSecret $k $keys[$k] }

    $desktop = [Environment]::GetFolderPath('Desktop')
    $keysFile = Join-Path $desktop 'claimradar-keys.txt'
    $lines = @("ClaimRadar BG keys - $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "Space: $SpaceId", '')
    foreach ($k in 'OWNER_KEY', 'ADMIN_KEY') { $lines += "$k=$($keys[$k])" }
    $lines += '', 'Пази този файл. Ползва се като header: x-admin-key: <ADMIN_KEY>'
    Set-Content -Path $keysFile -Value $lines -Encoding UTF8
    Say "Admin ключовете са записани в: $keysFile" 'Green'
}

# 4. По желание: OpenAI и база данни
$openai = Read-Secret "`nOPENAI_API_KEY (Enter = пропусни; без него AI verdict е изключен, приложението работи)"
if (-not [string]::IsNullOrWhiteSpace($openai)) { Set-SpaceSecret 'OPENAI_API_KEY' $openai.Trim() }

$dbUrl = Read-Secret 'DATABASE_URL на Supabase/Postgres (Enter = пропусни; ползва се JSONL)'
if (-not [string]::IsNullOrWhiteSpace($dbUrl)) { Set-SpaceSecret 'DATABASE_URL' $dbUrl.Trim() }

# 5. Сваляне на паузата + рестарт
Say "`nСвалям паузата и рестартирам Space-а..." 'Cyan'
Invoke-Hf 'POST' '/restart' | Out-Null

$deadline = (Get-Date).AddMinutes(20)
$last = ''
do {
    Start-Sleep -Seconds 15
    $runtime = Invoke-Hf 'GET' '/runtime'
    if ($runtime.stage -ne $last) { Say "  статус: $($runtime.stage)  ($(Get-Date -Format HH:mm:ss))"; $last = $runtime.stage }
    if ($runtime.stage -in 'BUILD_ERROR', 'RUNTIME_ERROR', 'CONFIG_ERROR', 'NO_APP_FILE') {
        Say "`nSpace-ът спря с $($runtime.stage): $($runtime.errorMessage)" 'Red'
        Say "Логове: https://huggingface.co/spaces/$SpaceId?logs=container" 'Red'
        Start-Process "https://huggingface.co/spaces/$SpaceId?logs=container"
        return
    }
} while ($runtime.stage -ne 'RUNNING' -and (Get-Date) -lt $deadline)

if ($runtime.stage -ne 'RUNNING') {
    Say "`nОще не е RUNNING след 20 минути (статус: $($runtime.stage)). Виж логовете:" 'Yellow'
    Say "https://huggingface.co/spaces/$SpaceId?logs=build" 'Yellow'
    return
}

# Проверка
Say "`nПроверявам живия сайт..." 'Cyan'
foreach ($path in '/health', '/') {
    try {
        $r = Invoke-WebRequest -Uri "$HfSpaceUrl$path" -UseBasicParsing -TimeoutSec 60
        Say "  $path -> $($r.StatusCode)" 'Green'
    } catch {
        Say "  $path -> ГРЕШКА: $($_.Exception.Message)" 'Red'
    }
}

Say "`nГотово. Сайтът: $HfSpaceUrl" 'Green'
if (-not $domainReady) {
    Say "`nЗа $CustomDomain остават 2 ръчни стъпки (нямат API):" 'Yellow'
    Say "  1) SuperHosting -> DNS на $RootDomain -> CNAME: claimradar -> hf.space (TTL 3600)"
    Say "  2) https://huggingface.co/spaces/$SpaceId/settings -> Custom Domain -> $CustomDomain (изисква HF PRO)"
    Say '  После пусни тази команда пак - ще превключи PUBLIC_BASE_URL към домейна.'
}
Start-Process $HfSpaceUrl
}
