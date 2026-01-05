# Batch Script Manager

A powerful, Python-based manager with a graphical user interface (GUI) to manage, monitor, and automate Windows batch scripts.

## Features

- **Centralized Control**: Start, stop, and restart multiple batch scripts from a single interface.
- **Real-time Monitoring**: Live display of console outputs (logs) for each script in dedicated tabs.
- **Autostart System**: Automatically launch scripts on program startup with a configurable delay (`global_start_delay_seconds`).
- **Resource Monitoring**: View Process IDs (PID) and CPU usage (requires `psutil`).
- **Notifications**: Desktop notifications for status changes (requires `plyer`).
- **Silent Mode**: Option to run the manager in the background without a console window.
- **Log Management**: Automatic logging of manager activities.

## Installation

1. **Install Python**: Ensure Python 3.x is installed on your system.
2. **Install Dependencies (optional but recommended)**:
   Open a terminal in the project folder and run:
   ```bash
   pip install psutil plyer
   ```

## Configuration

Configuration is handled via the [config.json](config.json) file. You can define your scripts here:

```json
{
    "scripts": {
        "My Script": {
            "path": "C:\\path\\to\\your\\script.bat",
            "autostart": true
        }
    },
    "global_start_delay_seconds": 5,
    "autostart_enabled": true
}
```

- `path`: Absolute path to the `.bat` file.
- `autostart`: Whether this specific script should start automatically.
- `global_start_delay_seconds`: Time in seconds between automatic starts of scripts.
- `autostart_enabled`: Global toggle for the autostart feature.

## Running the Program

There are three ways to start the manager:

1. **Normal Start**: Double-click [start_manager.bat](start_manager.bat).
2. **Silent Start (Background)**: Double-click [start_silent.vbs](start_silent.vbs). This starts the program without a visible console window.
3. **Via Command Line**:
   ```bash
   python batch_manager.py
   ```

## Project Structure

- [batch_manager.py](batch_manager.py): The main application (Python/Tkinter).
- [config.json](config.json): Configuration file for the managed scripts.
- [start_manager.bat](start_manager.bat): Batch file for easy startup.
- [start_silent.vbs](start_silent.vbs): VBScript for silent background startup.

## License

This project is licensed under the [MIT License](LICENSE).
