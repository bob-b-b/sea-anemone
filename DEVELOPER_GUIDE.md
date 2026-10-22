# Developer Guide - Building MyDashApp Distribution

## Quick Start for Developers

This guide walks you through creating a distributable Windows installer for your Dash app.

## Step-by-Step Build Process

### 1. Download Embedded Python

```
1. Visit: https://www.python.org/downloads/windows/
2. Find Python 3.12.x
3. Download: "Windows embeddable package (64-bit)"
4. Extract ALL files to: MyDashApp\python\
```

**Important:** The python folder should contain:
- python.exe
- python312.dll
- python312._pth
- All other Python files

### 2. Enable pip in Embedded Python

Open `python\python312._pth` and edit:

**Before:**
```
python312.zip
.
#import site
```

**After:**
```
python312.zip
.
import site
```

(Just remove the # from the last line)

### 3. Install Python Dependencies

Open Command Prompt in the MyDashApp folder and run:

```cmd
python\python.exe -m ensurepip
python\python.exe -m pip install --upgrade pip
python\python.exe -m pip install -r requirements.txt
```

This will take a few minutes to download and install Dash, Plotly, and Pandas.

### 4. Test Locally

Test that everything works before building the installer:

```cmd
run_app.bat
```

- A browser window should open automatically
- You should see your Dash app running
- Press Ctrl+C in the command window to stop

### 5. Install NSIS

Download and install NSIS (Nullsoft Scriptable Install System):
```
https://nsis.sourceforge.io/Download
```

Install it with default options.

### 6. Build the Installer

**Method 1: Right-click**
1. Right-click on `build_installer.nsi`
2. Select "Compile NSIS Script"

**Method 2: Command Line**
```cmd
"C:\Program Files (x86)\NSIS\makensis.exe" build_installer.nsi
```

This creates: `MyDashAppInstaller.exe`

### 7. Test the Installer

1. Copy `MyDashAppInstaller.exe` to a test location
2. Run it
3. Follow installation prompts
4. Test the installed app from the desktop shortcut

### 8. Distribute

Share `MyDashAppInstaller.exe` with users!

## File Structure Explained

```
MyDashApp/
├── python/                    # Embedded Python (you download this)
│   ├── python.exe
│   ├── python312.dll
│   ├── python312._pth        # EDIT THIS to enable pip!
│   └── ...
├── app/
│   ├── app.py                # Your main Dash app
│   ├── components/
│   │   └── layout.py         # Reusable components
│   └── assets/               # Auto-loaded by Dash
│       ├── styles.css        # CSS styling
│       └── script.js         # JavaScript
├── requirements.txt          # Python packages needed
├── setup.bat                 # Installs dependencies
├── run_app.bat              # Launches the app
├── build_installer.nsi      # NSIS installer script
└── README.md                # User documentation
```

## Customizing Your App

### Change App Name/Version

Edit `build_installer.nsi`:
```nsis
!define APPNAME "MyDashApp"      # Change this
!define VERSION "1.0"            # Change this
!define COMPANY "MyCompany"      # Change this
```

### Add More Python Packages

Edit `requirements.txt`:
```
dash==2.18.1
pandas==2.2.3
plotly==5.24.1
numpy==1.26.0        # Add new packages here
```

Then reinstall dependencies (step 3) and rebuild installer (step 6).

### Modify the UI

- **Layout**: Edit `app/components/layout.py`
- **Styling**: Edit `app/assets/styles.css`
- **JavaScript**: Edit `app/assets/script.js`
- **Main Logic**: Edit `app/app.py`

## Optional Performance Benchmarks

Install the development dependencies and run the opt-in benchmarks from the repository root:

```cmd
python -m pip install -r requirements-dev.txt
python -m pytest benchmarks\benchmark_sea_anemone.py --benchmark-only --benchmark-columns=mean,median,stddev
```

The suite measures USF archive loading, saved-session restoration, server-side Plotly figure rendering and JSON serialization, single-site inversion, and full inversion using the included 74-site sample archive. It is kept outside `tests/` so the benchmarks do not run as part of the regular CI test suite. Results are machine-dependent; compare runs on the same machine and dataset. These benchmarks do not measure browser rendering or end-to-end point-selection latency.

## Common Issues

### "pip not found"
- Make sure you edited `python312._pth` correctly
- Check that `import site` is uncommented (no # symbol)

### "Module not found" error when running
- Run the dependency installation again (step 3)
- Make sure all packages installed successfully

### Installer creates shortcuts but app won't run
- Test with `run_app.bat` first
- Check that `setup.bat` ran successfully during installation
- Make sure port 8050 is not in use

### Large installer size
- This is normal! Embedded Python + packages = ~150-250 MB
- You can use UPX to compress the executable

## Advanced: Updating the App

When you make changes:

1. Edit your app files
2. Test with `run_app.bat`
3. Update version in `build_installer.nsi`
4. Rebuild installer (step 6)
5. Distribute new installer

Users can install over the old version or uninstall first.

## Distribution Checklist

- [ ] Python embedded downloaded and extracted
- [ ] python312._pth modified to enable pip
- [ ] Dependencies installed locally
- [ ] App tested with run_app.bat
- [ ] NSIS installed
- [ ] Installer built successfully
- [ ] Installer tested on clean machine
- [ ] README.md updated for users
- [ ] Version number updated

## Tips

1. **Test on a clean Windows VM** - Best way to ensure it works for users
2. **Include version in filename** - E.g., `MyDashApp_v1.0_Installer.exe`
3. **Sign your installer** - For production, get a code signing certificate
4. **Compress with UPX** - Reduces installer size (optional)
5. **Auto-update mechanism** - Consider adding for future versions

## Support

Need help? Check:
- Dash documentation: https://dash.plotly.com/
- NSIS documentation: https://nsis.sourceforge.io/Docs/

Happy distributing! 🚀
