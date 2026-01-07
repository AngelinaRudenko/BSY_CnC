# BSY Command & Control (C&C) System

MQTT-based Command & Control system with controller and bot components using steganographic timezone-based communication protocol.

## Communication Protocol Design

This C&C system implements a novel covert communication protocol that disguises malicious traffic as legitimate IoT sensor data. The key design principle is that **detection is harder when traffic appears simple and valid** rather than encrypted and suspicious.

### Design Philosophy

The protocol is based on timezone synchronization data, which is a common and legitimate requirement for IoT devices. Rather than encrypting communications (which raises red flags during traffic analysis), the system uses **steganography** to hide commands and data within innocent-looking timezone information. This approach offers several advantages:

1. **Low Detection Risk**: Timezone data is common in IoT environments and doesn't trigger attention
2. **Readable Traffic**: Network analysts can read the data during inspection, but it appears benign
3. **No Encryption Signatures**: Avoids detection by systems that flag encrypted traffic

### Protocol Components

#### Message Structure

All messages are JSON objects disguised as IoT sensor data with the following fields:

- **`local_datetime`**: Legitimate timestamp (adds authenticity)
- **`device_id`**: Bot identifier disguised as a device ID (format: `SyncDevice####`)
- **`timezone`**: Command encoding field (controller → bot communication)
- **`timezones`**: Array of timezone strings for short message obfuscation (<=100 chars)
- **`datetime_leap`**: JSON-encoded timezone mapping for long message encryption (>100 chars)

#### Steganographic Encoding Methods

**1. Command Encoding (Controller → Bot)**
Commands are encoded as timezone strings using a predefined mapping:

| Command | Timezone | Action |
|---------|----------|--------|
| 1 | `America/New_York` | List alive bots (return IP) |
| 2 | `America/Los_Angeles` | List logged-in users |
| 3 | `America/Chicago` | List directory contents |
| 4 | `Europe/London` | Get user ID |
| 5 | `Europe/Paris` | Download file |
| 6 | `Europe/Berlin` | Execute binary |

The `local_datetime` field is set to the current time in the specified timezone to increase message authenticity.

**2. Character-Based Obfuscation (Short Messages)**
For messages <=100 characters, each character is mapped to a specific timezone. For example:
| Character | Timezone |
|---------|----------|
| a | `America/Argentina/Buenos_Aires` |
| A | `America/Anchorage` |
| B | `Europe/Berlin` |
| / | `America/Los_Angeles` |
| | ... |
 
Example: The path `/etc/passwd` becomes an array of timezones that appears as legitimate timezone configuration data.

**3. Base64 Distribution (Long Messages)**
For messages >100 characters (e.g., file contents):
1. Message is Base64-encoded
2. Encoded string is split into random-sized chunks (7-20 characters)
3. Chunks are distributed across timezone keys in a JSON object
4. The JSON structure mimics timezone configuration files

This method is used for file exfiltration, appearing as timezone data synchronization.

#### Traffic Example

**Controller Command** (List directory):
```json
{
  "local_datetime": "2026-01-07T15:30:45-06:00",
  "timezone": "America/Chicago",
  "timezones": ["America/Los_Angeles", "Europe/Madrid", ...]
}
```

**Bot Response** (with file contents):
```json
{
  "local_datetime": "2026-01-07T22:31:12",
  "device_id": "SyncDevice4257",
  "datetime_leap": "{\"America/New_York\": [\"aGVsbG8=\", \"d29ybGQ=\"], ...}"
}
```

To a casual observer, this appears to be IoT devices synchronizing timezone information and reporting their status.

### Security Features

- **Message Filtering**: Both controller and bot ignore messages from unrecognized devices
- **Stealth Operation**: Failed parsing of messages is silently ignored (no error messages)
- **Device Masquerading**: Bot IDs use format `SyncDevice####` to appear as legitimate sync clients
- **No Encryption Artifacts**: Avoids TLS/encryption detection systems

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