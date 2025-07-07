import logging
from logging.handlers import RotatingFileHandler
import os

# Ensure log directory exists
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, 'app.log')

# 128 MB = 134217728 bytes
MAX_LOG_SIZE = 128 * 1024 * 1024
BACKUP_COUNT = 5  # Number of backup files to keep

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding='utf-8'),
        logging.StreamHandler()
    ]
) 