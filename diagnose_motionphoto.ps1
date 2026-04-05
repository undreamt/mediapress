param(
    [Parameter(Mandatory=$true)]
    [string]$Photo
)

if (-not (Test-Path $Photo)) {
    Write-Host "File not found: $Photo"
    exit 1
}

$bytes = [System.IO.File]::ReadAllBytes($Photo)
Write-Host "File size: $($bytes.Length) bytes"

# Check XMP for MicroVideoOffset (search first 64KB)
$xmp = [System.Text.Encoding]::ASCII.GetString($bytes[0..([Math]::Min(65535, $bytes.Length-1))])
$marker = "MicroVideoOffset="
$xmpIdx = $xmp.IndexOf($marker)
if ($xmpIdx -ge 0) {
    $val = $xmp.Substring($xmpIdx + $marker.Length, 20) -replace '[^0-9].*',''
    $xmpStart = $bytes.Length - [int]$val
    Write-Host "XMP MicroVideoOffset=$val  => video starts at byte $xmpStart"
} else {
    Write-Host "No XMP MicroVideoOffset found"
}

# Search ENTIRE file for ftyp
Write-Host "Scanning full file for ftyp..."
$found = @()
for ($i = 4; $i -lt $bytes.Length - 4; $i++) {
    if ($bytes[$i] -eq 102 -and $bytes[$i+1] -eq 116 -and $bytes[$i+2] -eq 121 -and $bytes[$i+3] -eq 112) {
        $b0 = [int]$bytes[$i-4]
        $b1 = [int]$bytes[$i-3]
        $b2 = [int]$bytes[$i-2]
        $b3 = [int]$bytes[$i-1]
        $boxSize = ($b0 -shl 24) -bor ($b1 -shl 16) -bor ($b2 -shl 8) -bor $b3
        Write-Host "  ftyp at byte $i  (box start: $($i-4)  box size: $boxSize)"
        $found += ($i - 4)
    }
}

if ($found.Count -eq 0) {
    Write-Host "No ftyp found anywhere in file - not a motion photo"
    exit 1
}

# Use the LAST ftyp box start as the video offset
$offset = $found[-1]
Write-Host ""
Write-Host "Extracting from offset $offset ..."
$videoBytes = $bytes[$offset..($bytes.Length - 1)]
$tmpFile = "$env:TEMP\mp_extract.mp4"
$outFile  = "$env:TEMP\mp_output.mp4"
[System.IO.File]::WriteAllBytes($tmpFile, $videoBytes)
Write-Host "Extracted $($videoBytes.Length) bytes to $tmpFile"
Write-Host ""

Write-Host "=== ffprobe ==="
& ffprobe -v error -show_streams -show_format $tmpFile
Write-Host ""

Write-Host "=== ffmpeg encode ==="
& ffmpeg -loglevel error -i $tmpFile -c:v libx264 -crf 23 -preset medium -an -movflags +faststart -y $outFile
if (Test-Path $outFile) {
    $sz = (Get-Item $outFile).Length
    Write-Host "Output: $sz bytes at $outFile"
} else {
    Write-Host "Output file was NOT created"
}
