@echo off
echo Setting up Anemone...

:: Install required Python packages
if exist requirements.txt (
    echo Installing dependencies...
    python\python.exe -m pip install --no-cache-dir -r requirements.txt
) else (
    echo requirements.txt not found. Skipping dependency installation.
)

echo Setup complete. You can now run the application using run_app.bat