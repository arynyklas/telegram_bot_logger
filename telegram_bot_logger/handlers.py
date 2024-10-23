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


class DebugQueueListener(QueueListener):
    """If our background thread fails, we need to have at least some indication about it.

    We just dump the exception to the stdout.
    """
    def handle(self, record):
        try:
            super().handle(record)
        except Exception as e:
            print(f"Error handling record: {e}")
            print(f"Record: {vars(record)}")
            import traceback
            traceback.print_exc()
            raise


class TelegramMessageHandler(QueueHandler):
    def __init__(
        self,
        bot_token: str,
        chat_ids: Union[int, str, CHAT_IDS_T],
        api_server: Optional[_api_server.TelegramAPIServer]=_api_server.PRODUCTION_SERVER,
        format_type: Optional[Union[formatters.FormatType, str]]=formatters.FormatType.TEXT,
        document_name_strategy: Optional[Union[formatters.DocumentNameStrategy, str]]=formatters.DocumentNameStrategy.TIMESTAMP,
        proxies: Optional[PROXIES_T]=None,
        formatter: Optional[formatters.TelegramBaseFormatter]=formatters.TelegramHTMLTextFormatter(),
        additional_body: Optional[ADDITIONAL_BODY_T]=None,
        level: Optional[str]=None
    ) -> None:
        if not isinstance(chat_ids, list):
            chat_ids = [chat_ids]

        temp_chat_ids: CHAT_IDS_T = chat_ids.copy()

        for index, chat_id in enumerate(temp_chat_ids, 0):
            chat_id_class = type(chat_id)

            if chat_id_class not in (int, str):
                raise ValueError("Chat ids are incorrect!")

            if chat_id_class == str:
                if not chat_id:
                    raise ValueError(f"Chat id {chat_id!r} is incorrect!")

                if chat_id[0] == "-":
                    raise ValueError(f"Pass group chat ids as integers, not strings")

                if chat_id[0] != "@":
                    chat_ids[index] = "@" + chat_id

        self.queue: Queue = Queue()

        super().__init__(
            queue = self.queue
        )

        if isinstance(format_type, str):
            try:
                format_type = formatters.FormatType.__getitem__(format_type.upper())
            except KeyError:
                pass

        if not isinstance(format_type, formatters.FormatType):
            raise ValueError("Only string or enum of formatters.FormatType can be passed.")

        if isinstance(document_name_strategy, str):
            try:
                document_name_strategy = formatters.DocumentNameStrategy.__getitem__(document_name_strategy.upper())
            except KeyError:
                pass

        if not isinstance(document_name_strategy, formatters.DocumentNameStrategy):
            raise ValueError("Only string or enum of formatters.DocumentNameStrategy can be passed.")

        if level:
            self.setLevel(
                level = level
            )

        self.handler: InnerTelegramMessageHandler = InnerTelegramMessageHandler(
            bot_token = bot_token,
            chat_ids = chat_ids,
            api_server = api_server,
            format_type = format_type,
            document_name_strategy = document_name_strategy,
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
            raise ValueError("Formatter class must be subclass of formatters.TelegramBaseFormatter")

        self.handler.setFormatter(
            fmt = formatter
        )

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record

    def close(self) -> None:
        if self.listener is not None:
            # Avoid double shutdown
            self.listener.stop()
            self.listener = None
        super().close()


class InnerTelegramMessageHandler(logging.Handler):
    def __init__(
        self,
        bot_token: str,
        chat_ids: CHAT_IDS_T,
        api_server: _api_server.TelegramAPIServer,
        format_type: formatters.FormatType,
        document_name_strategy: formatters.DocumentNameStrategy,
        proxies: Optional[PROXIES_T]=None,
        additional_body: Optional[ADDITIONAL_BODY_T]=None
    ):
        self.bot_token: str = bot_token
        self.chat_ids: CHAT_IDS_T = chat_ids
        self.api_server: _api_server.TelegramAPIServer = api_server
        self.format_type: formatters.FormatType = format_type
        self.document_name_strategy: formatters.DocumentNameStrategy = document_name_strategy
        self.additional_body: ADDITIONAL_BODY_T = additional_body or dict()

        self.http_client: _HTTPClient = _HTTPClient(
            proxies = proxies
        )

        super().__init__()

        self.formatter: formatters.TelegramBaseFormatter

    def _build_http_request_body(self, chat_id: int) -> REQUEST_BODY_T:
        request_body: ADDITIONAL_BODY_T = self.additional_body.copy()
        request_body["chat_id"] = chat_id

        if self.formatter.PARSE_MODE:
            request_body["parse_mode"] = self.formatter.PARSE_MODE

        return request_body

    def _check_telegram_answer(self, http_response: _HTTPResponse, chat_id: int) -> None:
        if http_response.status_code != 200:
            logger.warning(f"Request to Telegram got error: {http_response.status_code} | {http_response.text}")

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

    def send_document_message(self, chat_id: int, filename: str, bytes_content: bytes, text: Optional[str]=None) -> None:
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
                    "{filename}.txt".format(
                        filename = filename
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

        if self.format_type == formatters.FormatType.TEXT:
            text_fragments: formatters.TEXT_FRAGMENTS_T = self.formatter.format_by_fragments(
                record = record
            )

        else:
            bytes_content: bytes = self.formatter.format_raw(
                record = record
            ).encode("utf-8")

            tag_text: Union[str, None] = (
                self.formatter.format_tag(
                    record = record
                )
                if self.formatter.format_tag != formatters.TelegramBaseFormatter.format_tag
                else
                None
            )

        for chat_id in self.chat_ids:
            if self.format_type == formatters.FormatType.TEXT:
                for text_fragment in text_fragments:
                    self.send_text_message(
                        chat_id = chat_id,
                        text = text_fragment
                    )

            else:
                self.send_document_message(
                    chat_id = chat_id,
                    filename = (
                        str(int(record.created))
                        if self.document_name_strategy == formatters.DocumentNameStrategy.TIMESTAMP
                        else
                        record.__dict__["document_name"]
                    ),
                    bytes_content = bytes_content,
                    text = tag_text
                )
