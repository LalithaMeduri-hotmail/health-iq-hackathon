#Requires -Version 7.0
# Opens a Health IQ share link the way a doctor's browser would, to confirm it resolves.
param([Parameter(Mandatory)][string]$Url)

$response = Invoke-WebRequest -Uri $Url -TimeoutSec 60 -SkipHttpErrorCheck
$contentType = $response.Headers['Content-Type']
$disposition = $response.Headers['Content-Disposition']
Write-Host "status=$($response.StatusCode) type=$contentType bytes=$($response.RawContentLength)"
Write-Host "disposition=$disposition"
