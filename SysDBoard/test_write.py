import os
import json
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_file.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

try:
    logger.debug("Testing file write")
    config = {"test": {"x": 100, "y": 100}}
    with open("test_config.json", "w") as f:
        json.dump(config, f, indent=4)
    logger.debug("File write successful")
    if os.path.exists("test_config.json"):
        logger.debug("File exists")
    else:
        logger.error("File not found")
except Exception as e:
    logger.error(f"File write failed: {e}")
    print(f"Error: {e}")