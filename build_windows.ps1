$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3 -m pip install -r requirements-build.txt
py -3 -m PyInstaller --noconfirm --clean --onedir --console --name SmartQLVB --add-data "index.html;." --collect-all fitz server.py
Copy-Item -Recurse -Force TIEN_ICH_TRINH_DUYET dist/SmartQLVB/TIEN_ICH_TRINH_DUYET
Copy-Item -Force README_CAI_DAT.txt dist/SmartQLVB/README_CAI_DAT.txt
Compress-Archive -Path dist/SmartQLVB -DestinationPath dist/SmartQLVB_Windows_x64.zip -Force
Write-Host 'Da tao: dist/SmartQLVB_Windows_x64.zip'
