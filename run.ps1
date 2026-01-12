Write-Host "Setting environment variables..."
$env:GOOGLE_API_KEY = "AIzaSyC1ptxK5KNrvChI5yY1Bju2e6dZMuIwXME"
Write-Host "Installing dependencies..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install dependencies. Please check your Python and pip installation."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Starting Flask app..."
python app.py
