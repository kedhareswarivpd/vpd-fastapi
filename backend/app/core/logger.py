import logging
import logging.handlers
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("vpdtechnologies")
logger.setLevel(logging.DEBUG)

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_console = logging.StreamHandler()
_console.setFormatter(_formatter)
logger.addHandler(_console)

_file = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, "combined.log"), maxBytes=5_000_000, backupCount=5
)
_file.setFormatter(_formatter)
logger.addHandler(_file)

_error_file = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, "error.log"), maxBytes=5_000_000, backupCount=5
)
_error_file.setLevel(logging.ERROR)
_error_file.setFormatter(_formatter)
logger.addHandler(_error_file)
