param([Parameter(Mandatory=$true)][string]$RequestPath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Speech
$taskRequest = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskVoices = @($taskSynth.GetInstalledVoices() | Where-Object Enabled | ForEach-Object {
        @{name=$_.VoiceInfo.Name; culture=$_.VoiceInfo.Culture.Name; gender=$_.VoiceInfo.Gender.ToString()}
    })
    if ($taskRequest.action -eq 'voices') {
        @{engine='windows-sapi'; voices=$taskVoices} | ConvertTo-Json -Depth 4 -Compress
    } elseif ($taskRequest.action -eq 'speak') {
        if (-not ($taskVoices | Where-Object {$_.name -eq $taskRequest.voice})) { throw 'Requested voice is not installed' }
        if ([int]$taskRequest.rate -lt -10 -or [int]$taskRequest.rate -gt 10) { throw 'Invalid rate' }
        $taskSynth.SelectVoice([string]$taskRequest.voice)
        $taskSynth.Rate = [int]$taskRequest.rate
        $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $taskSynth.SetOutputToWaveFile([string]$taskRequest.output, $taskFormat)
        $taskSynth.Speak([string]$taskRequest.text)
        $taskSynth.SetOutputToNull()
        @{voice=$taskSynth.Voice.Name; culture=$taskSynth.Voice.Culture.Name; rate=$taskSynth.Rate} | ConvertTo-Json -Compress
    } else { throw 'Unsupported action' }
} finally { $taskSynth.Dispose() }