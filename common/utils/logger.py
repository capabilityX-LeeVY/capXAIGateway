import logging
from datetime import datetime
import threading
import os
import sys

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# Try to get LOG_PATH from environment, fallback to default
LOG_PATH = os.environ.get('LOG_PATH', 'logs')

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

def safe_unicode_message(message):
    """
    Convert Unicode characters that might cause encoding issues to safe alternatives.
    This is particularly important for Windows console output.
    """
    if not isinstance(message, str):
        message = str(message)
    
    # Replace common Unicode characters that cause issues in Windows console
    unicode_replacements = {
        '✅': '[SUCCESS]',
        '❌': '[FAILURE]',
        '⚠️': '[WARNING]',
        '💡': '[INFO]',
        '🔧': '[CONFIG]',
        '🚀': '[START]',
        '📁': '[FOLDER]',
        '🔨': '[BUILD]',
        '⚪': '[PENDING]',
        '✓': '[OK]',
        '✗': '[FAIL]',
        '→': '->',
        '←': '<-',
        '↑': '^',
        '↓': 'v',
    }
    
    for unicode_char, replacement in unicode_replacements.items():
        message = message.replace(unicode_char, replacement)
    
    # Handle any remaining Unicode characters that might cause issues
    try:
        # Try to encode with the system's default encoding
        if sys.platform.startswith('win'):
            # For Windows, try cp1252 first, then fallback to ascii
            try:
                message.encode('cp1252')
            except UnicodeEncodeError:
                message = message.encode('ascii', errors='replace').decode('ascii')
    except Exception:
        # Ultimate fallback: convert to ASCII with replacement
        message = message.encode('ascii', errors='replace').decode('ascii')
    
    return message

def formatter_message(message, use_color = True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message

MESSAGE_COLORS = ["BLACK","RED","GREEN","YELLOW","BLUE","MAGENTA","CYAN","WHITE"]

COLORS = {
    'DEBUG': BLUE,
    'INFO': GREEN,
    'WARNING': YELLOW,
    'ERROR': RED,
    'CRITICAL': RED,
    "BLACK":BLACK,
    "RED":RED,
    "GREEN":GREEN,
    "YELLOW":YELLOW,
    "BLUE":BLUE,
    "MAGENTA":MAGENTA,
    "CYAN":CYAN,
    "WHITE":WHITE,
}

class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, message_color =1, use_color = True):
        logging.Formatter.__init__(self, msg)
        self.use_color = use_color


    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            levelname_color = COLOR_SEQ % (30 + COLORS[levelname]) + "[" + levelname +"]" + RESET_SEQ
            record.levelname = levelname_color
            record.msg = COLOR_SEQ % (30 + COLORS[levelname])  + record.msg  + RESET_SEQ

        return logging.Formatter.format(self, record)


class CColorLogger(object):
    _instance_lock = threading.Lock()
    def __init__(self) -> None:
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(CColorLogger, "_instance"):
            with CColorLogger._instance_lock:
                if not hasattr(CColorLogger, "_instance"):
                    CColorLogger._instance = object.__new__(cls)
                    CColorLogger._instance.initLogger("capx") 
        return CColorLogger._instance
    
    def initLogger(self,logName):
        self.logger = logging.getLogger(logName)
        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)
        # print(f"Log path: {LOG_PATH}")
        filename = f'''{LOG_PATH}/{logName}_{datetime.now().date()}.log'''
        fileHandler = logging.FileHandler(filename,mode="w+",encoding="utf-8")
        
        BASIC_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
        formatter = logging.Formatter(BASIC_FORMAT)
        fileHandler.setFormatter(formatter)
        fileHandler.setLevel(logging.DEBUG)

        FORMAT = "$RESET $BOLD %(levelname)-10s $RESET %(message)s"
        COLOR_FORMAT = formatter_message(FORMAT, True)
        color_formatter = ColoredFormatter(COLOR_FORMAT)
        console = logging.StreamHandler()
        console.setFormatter(color_formatter)
        console.setLevel(logging.INFO)
        self.logger.setLevel(logging.DEBUG)

        self.logger.addHandler(fileHandler)
        self.logger.addHandler(console)

    def debug(self,message,color:str = "BLUE"):
        if self.logger is None:
            return
        safe_message = safe_unicode_message(message)
        self.logger.debug(safe_message)


    def info(self,message,color:str = "GREEN"):
        if self.logger is None:
            return 
        safe_message = safe_unicode_message(message)
        self.logger.info(safe_message)

    def warning(self,message,color:str = "YELLOW"):
        if self.logger is None:
            return 
        safe_message = safe_unicode_message(message)
        self.logger.warning(safe_message)  

    def error(self,message,color:str = "RED"):
        if self.logger is None:
            return 
        safe_message = safe_unicode_message(message)
        self.logger.error(safe_message)  


def LOGGER_DEBUG(message,color:str = "WHITE"):
    logger = CColorLogger()
    logger.debug(message,color)

def LOGGER_INFO(message,color:str = "WHITE"):
    logger = CColorLogger()
    logger.info(message,color)

def LOGGER_WARNING(message,color:str = "WHITE"):
    logger = CColorLogger()
    logger.warning(message,color)

def LOGGER_ERROR(message,color:str = "WHITE"):
    logger = CColorLogger()
    logger.error(message,color)
    
if __name__ == "__main__":
    for color in MESSAGE_COLORS:
        LOGGER_DEBUG("ABC",)
        LOGGER_DEBUG("AAAA",color)
        LOGGER_INFO("BBB",color)
        LOGGER_WARNING("CCC",color)
        LOGGER_ERROR("DDD",color)






