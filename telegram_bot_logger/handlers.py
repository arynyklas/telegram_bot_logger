from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from httpx import Client as _HTTPClient, Response as _HTTPResponse

import logging

from . import formatters, api_server as _api_server

from typing import Union, List, Optional, Dict, Any


CHAT_IDS_T = List[Union[int, str]]
PROXIES_T = Dict[str, str]
ADDITIONAL_BODY_T = Dict[str, Any]
REQUEST_BODY_T = Dict[str, Any]


logger: logging.Logger = logging.getLogger(__name__)


class TelegramMessageHandler(QueueHandler):
    def __init__(
        self,
        chat_ids: Union[int, str, CHAT_IDS_T],
        bot_token: str,
        api_server: Optional[_api_server.TelegramAPIServer]=_api_server.PRODUCTION_SERVER,
        format_type: Optional[formatters.FormatTypes]=formatters.FormatTypes.TEXT,
        proxies: Optional[PROXIES_T]=None,
        formatter: Optional[formatters.TelegramBaseFormatter]=formatters.TelegramHTMLTextFormatter(),
        additional_body: Optional[ADDITIONAL_BODY_T]=None
    ) -> None:
        if not isinstance(chat_ids, list):
            chat_ids = [chat_ids]

        self.queue: Queue = Queue()

        super().__init__(
            queue = self.queue
        )

        self.handler: InnerTelegramMessageHandler = InnerTelegramMessageHandler(
            chat_ids = chat_ids,
            bot_token = bot_token,
            api_server = api_server,
            format_type = format_type,
            proxies = proxies,
            additional_body = additional_body
        )

        self.handler.setFormatter(
            fmt = formatter
        )

        self.listener: QueueListener = QueueListener(
            self.queue,
            self.handler
        )

        self.listener.start()

    def setFormatter(self, formatter: formatters.TelegramBaseFormatter) -> None:
        if not isinstance(formatter, formatters.TelegramBaseFormatter):
            raise ValueError("Formatter class must be subclass of telegram_bot_logger.formatters.TelegramBaseFormatter")

        self.handler.setFormatter(
            fmt = formatter
        )

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record

    def close(self) -> None:
        self.listener.stop()
        super().close()


class InnerTelegramMessageHandler(logging.Handler):
    def __init__(
        self,
        chat_ids: CHAT_IDS_T,
        bot_token: str,
        api_server: _api_server.TelegramAPIServer,
        format_type: formatters.FormatTypes,
        proxies: Optional[PROXIES_T]=None,
        additional_body: Optional[ADDITIONAL_BODY_T]=None,
        *args,
        **kwargs
    ):
        self.chat_ids: CHAT_IDS_T = chat_ids
        self.bot_token: str = bot_token
        self.api_server: _api_server.TelegramAPIServer = api_server
        self.format_type: formatters.FormatTypes = format_type
        self.additional_body: ADDITIONAL_BODY_T = additional_body or dict()

        self.http_client: _HTTPClient = _HTTPClient(
            proxies = proxies
        )

        super().__init__(*args, **kwargs)

        self.formatter: Union[formatters.TelegramBaseFormatter, None] = None

    def _build_http_request_body(self, chat_id: int) -> REQUEST_BODY_T:
        request_body: ADDITIONAL_BODY_T = self.additional_body.copy()
        request_body["chat_id"] = chat_id

        if self.formatter.PARSE_MODE:
            request_body["parse_mode"] = self.formatter.PARSE_MODE

        return request_body

    def _check_telegram_answer(self, http_response: _HTTPResponse, chat_id: int) -> None:
        if http_response.status_code != 200:
            logger.warning(f"Request to telegram got error with code: {http_response.status_code}")
            logger.warning(f"Response is: {http_response.text}")

        response_dict: dict = http_response.json()

        if not response_dict["ok"]:
            logger.warning(f"""Failed to send log message to chat {chat_id}: {response_dict["description"]}""")

    def send_text_message(self, chat_id: int, text: str) -> None:
        request_body: ADDITIONAL_BODY_T = self._build_http_request_body(
            chat_id = chat_id
        )

        request_body["text"] = text

        http_response: _HTTPResponse = self.http_client.post(
            url = self.api_server.api_url(
                bot_token = self.bot_token,
                method = "sendMessage"
            ),
            json = request_body
        )

        self._check_telegram_answer(
            http_response = http_response,
            chat_id = chat_id
        )

    def send_document_message(self, chat_id: int, timestamp: int, bytes_content: bytes, text: Optional[str]=None) -> None:
        request_body: ADDITIONAL_BODY_T = self._build_http_request_body(
            chat_id = chat_id
        )

        if text:
            request_body["caption"] = text

        http_response: _HTTPResponse = self.http_client.post(
            url = self.api_server.api_url(
                bot_token = self.bot_token,
                method = "sendDocument"
            ),
            data = request_body,
            files = {
                "document": (
                    "{timestamp}.txt".format(
                        timestamp = timestamp
                    ),
                    bytes_content,
                    "text/plain"
                )
            }
        )

        self._check_telegram_answer(
            http_response = http_response,
            chat_id = chat_id
        )

    def emit(self, record: logging.LogRecord) -> None:
        self.formatter.prepare(
            record = record
        )

        if self.format_type == formatters.FormatTypes.TEXT:
            text_fragments: formatters.TEXT_FRAGMENTS_T = self.formatter.format_by_fragments(
                record = record
            )

        else:
            bytes_content: bytes = self.formatter.format(
                record = record
            ).encode("utf-8")

            tag_text: Union[str, None] = (
                getattr(
                    self.formatter,
                    "get_record_tag"
                )(record)
                if hasattr(self.formatter, "get_record_tag")
                else
                None
            )

        for chat_id in self.chat_ids:
            if self.format_type == formatters.FormatTypes.TEXT:
                for text in text_fragments:
                    self.send_text_message(
                        chat_id = chat_id,
                        text = text
                    )

            else:
                self.send_document_message(
                    chat_id = chat_id,
                    timestamp = int(record.created),
                    bytes_content = bytes_content,
                    text = tag_text
                )
