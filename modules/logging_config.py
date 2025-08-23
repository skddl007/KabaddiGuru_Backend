import logging

def configure_logging():
    logging.basicConfig(
        filename="query_logs.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
