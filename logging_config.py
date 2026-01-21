import logging
import os
from pythonjsonlogger import jsonlogger

def setup_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    service_name = os.getenv("SERVICE_NAME", "my-service")
    env = os.getenv("ENV", "dev")

    handler = logging.StreamHandler()  # stdout

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s "
        "%(service)s %(env)s"
    )

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()   # IMPORTANT for uvicorn/gunicorn
    root_logger.addHandler(handler)

    # Add default fields to all logs
    root_logger = logging.LoggerAdapter(
        root_logger,
        {
            "service": service_name,
            "env": env,
        }
    )

    return root_logger
