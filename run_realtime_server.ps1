param(
  [string]$Model = "small",
  [string]$Device = "cpu",
  [string]$ComputeType = "int8",
  [int]$Port = 7861,
  [double]$Interval = 1.6
)

Set-Location $PSScriptRoot

if (!(Test-Path ".venv")) {
  python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

$env:WHISPER_MODEL_SIZE = $Model
$env:WHISPER_DEVICE = $Device
$env:WHISPER_COMPUTE_TYPE = $ComputeType
$env:STREAM_PORT = "$Port"
$env:REALTIME_INTERVAL = "$Interval"

python streaming_server.py
