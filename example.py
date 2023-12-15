import telegram_bot_logger

import logging


logger: logging.Logger = logging.getLogger("telegram_bot_logger_example")

handler: telegram_bot_logger.TelegramMessageHandler = telegram_bot_logger.TelegramMessageHandler(
    bot_token = input("Enter bot token: "),
    chat_ids = [
        int(input("Enter chat ID: "))
    ],
    format_type = input("Enter format type (or skip): ").strip() or telegram_bot_logger.formatters.FormatType.TEXT,
    document_name_strategy = input("Enter document name strategy (or skip): ").strip() or telegram_bot_logger.formatters.DocumentNameStrategy.TIMESTAMP
)

logger.setLevel(
    level = logging.DEBUG
)

logger.addHandler(handler)


logger.debug("debug-message", extra={"document_name": "debug-doc-name"})
logger.info("info-message", extra={"document_name": "info-doc-name"})
logger.warning("warning-message", extra={"document_name": "warning-doc-name"})
logger.error("error-message", extra={"document_name": "error-doc-name"})

try:
    1/0
except Exception as ex:
    logger.exception("exception-message", exc_info=ex, extra={"document_name": "exception-doc-name"})

logger.critical("critical-message", extra={"document_name": "critical-doc-name"})

logger.info(f"info-long-message {'0' * 4096}", extra={"document_name": "long-doc-name"})
