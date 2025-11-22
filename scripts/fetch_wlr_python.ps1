# PowerShell version of fetch_wlr_python.sh for Windows users
# Downloads the WLR AIO CPython WASM binary

# Update these to the latest python AIO release from vmware-labs/webassembly-language-runtimes
# See: https://github.com/vmware-labs/webassembly-language-runtimes/releases
$WLR_RELEASE_TAG = "python/3.12.0+20231211-040d5a6"
$AIO_FILE = "python-3.12.0.wasm"

# Create bin directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "bin" | Out-Null

# Download the WASM binary (25.1 MB)
$url = "https://github.com/vmware-labs/webassembly-language-runtimes/releases/download/$WLR_RELEASE_TAG/$AIO_FILE"
Write-Host "Downloading python.wasm from $url..."

Invoke-WebRequest -Uri $url -OutFile "bin\python.wasm"

Write-Host "Downloaded bin\python.wasm successfully!"
