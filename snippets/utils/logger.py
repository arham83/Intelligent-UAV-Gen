import logging
import os
from datetime import datetime

class LoggerManager:
    def __init__(self, name='Logger', log_dir='logs', level=logging.INFO):
        self.name = name
        self.log_dir = log_dir
        self.level = level
        self.logger = self._setup_logger()

    def _setup_logger(self):
        os.makedirs(self.log_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file = os.path.join(self.log_dir, f'{self.name}_{timestamp}.log')

        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        logger.propagate = False

        if logger.hasHandlers():
            logger.handlers.clear()

        # Only file handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(self.level)
        fh_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
        fh.setFormatter(fh_formatter)

        logger.addHandler(fh)

        return logger

    def get_logger(self):
        return self.logger
