# MyDashApp

## Overview
MyDashApp is a Dash application designed for interactive web-based data visualization. This project includes all necessary components to run the application locally without requiring a separate Python installation.

## Project Structure
```
MyDashApp
├── app
│   ├── app.py               # Main entry point of the Dash application
│   ├── assets
│   │   ├── styles.css       # CSS styles for the application
│   │   └── script.js        # Custom JavaScript for interactivity
│   └── components
│       └── layout.py        # Layout definition for the application
├── python                    # Embedded Python distribution files
├── build_installer.nsi      # Installer script for packaging the application
├── setup.bat                # Batch file to set up the application environment
├── run_app.bat              # Batch file to launch the Dash application
├── requirements.txt          # Python packages required for the application
├── package.json              # npm configuration file (if applicable)
└── README.md                 # Documentation for the project
```

## Installation
To install MyDashApp, follow these steps:

1. **Run the Installer**: Execute the `MyDashAppInstaller.exe` to install the application. This will copy the necessary files to your Program Files directory and create shortcuts for easy access.

2. **Set Up the Environment**: If you prefer to set up the application manually, run `setup.bat` to install the required Python packages listed in `requirements.txt`.

## Usage
To launch the application, you can either:

- Use the shortcut created in the Start Menu or on your Desktop.
- Run `run_app.bat` from the installation directory.

## Requirements
Ensure you have the following before running the application:

- Windows operating system
- No separate Python installation is required, as the application includes an embedded Python distribution.

## Contributing
If you would like to contribute to MyDashApp, please fork the repository and submit a pull request with your changes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.