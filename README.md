# BSY Command & Control (C&C) System

MQTT-based Command & Control system with controller and bot components.

## Prerequisites

- Python 3.9 or higher
- Access to MQTT broker (configured at 147.32.82.209:1883)

## Setup

### 1. Create Virtual Environment

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 2. Install Dependencies

**Linux/Mac/Windows:**
```bash
pip install -r requirements.txt
```

## Running the Project

### Start the Bot

The bot listens for commands from the controller and executes them.

**Linux/Mac/Windows:**
```bash
python3 bot.py
```

### Start the Controller

The controller sends commands to connected bots.

**Linux/Mac/Windows:**
```bash
python3 controller.py
```

## Deactivating Virtual Environment

When you're done, deactivate the virtual environment:

```bash
deactivate
```

# Sources

- [MQTT Python Tutorial - YouTube](https://www.youtube.com/watch?v=kuyCd53AOtg&pp=ygULTVFUVCBweXRob24%3D)
- [Paho MQTT Python Client Documentation](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)
- [Python Documentation - W3Schools](https://www.w3schools.com/python/)