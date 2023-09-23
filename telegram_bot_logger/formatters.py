from enum import Enum as _Enum, auto as _enum_auto

import logging

from . import utils

from typing import List, Union, Dict


TEXT_FRAGMENTS_T = List[str]


class FormatType(_Enum):
    TEXT = _enum_auto()
    DOCUMENT = _enum_auto()


class TelegramBaseFormatter(logging.Formatter):
    PARSE_MODE: Union[str, None] = None

    _MAX_TEXT_SIZE: int = 4096
    _MAX_MESSAGE_SIZE: int = 100
    _MESSAGE_CONTINUE: str = "..."
    _MESSAGE_CONTINUE_LENGTH: int = len(_MESSAGE_CONTINUE)

    def format_raw(self, record: logging.LogRecord) -> str:
        return self.format(
            record = record
        )

    def format_by_fragments(self, record: logging.LogRecord) -> TEXT_FRAGMENTS_T:
        raise NotImplementedError

    def prepare(self, record: logging.LogRecord) -> None:
        message: str = record.msg

        if len(message) > self._MAX_MESSAGE_SIZE + self._MESSAGE_CONTINUE_LENGTH:
            message = message[:self._MAX_MESSAGE_SIZE] + self._MESSAGE_CONTINUE

        record.message = message

    def format_tag(self, record: logging.LogRecord) -> str:
        raise NotImplementedError


class TelegramRawTextFormatter(TelegramBaseFormatter):
    def format_by_fragments(self, record: logging.LogRecord) -> TEXT_FRAGMENTS_T:
        text: str = self.format()

        if len(text) <= self._MAX_TEXT_SIZE:
            return [text]

        tag_text: str = (
            self.format_tag(record)
            if self.format_tag != TelegramBaseFormatter.format_tag
            else
            ""
        )

        end_index: int = text.find(record.exc_text)

        max_fragment_length: int = self._MAX_TEXT_SIZE - len(tag_text)

        fragments: TEXT_FRAGMENTS_T = [
            text[:end_index] + tag_text,
            *[
                text[index:index + max_fragment_length] + tag_text
                for index in range(end_index, len(text[end_index:]), max_fragment_length)
            ]
        ]

        return fragments


class TelegramHTMLTextFormatter(TelegramBaseFormatter):
    PARSE_MODE = "html"

    _EMOTICONS: Dict[int, str] = {
        logging.DEBUG: "🔧",
        logging.INFO: "ℹ️",
        logging.WARNING: "⚠️",
        logging.ERROR: "🔥",
        logging.CRITICAL: "❌"
    }

    _TAG_FORMAT: str = "#logl{level_name} #logt{timestamp}"
    _HEADER_FORMAT: str = "{emoticon} - <i>{name}</i> - (<code>{module}</code>).<code>{func_name}</code>(<code>{lineno}</code>) - <pre>{message}{description}</pre>"
    _RAW_FORMAT: str = "{level_name} - {name} - ({module}).{func_name}({lineno}) - {message}{description}"
    _DESCRIPTION_FORMAT: str = "\n\n{description}"

    _HTML_CODE_START: str = "<pre>"
    _HTML_CODE_END: str = "</pre>"
    _HTML_CODE_LENGTH: int = len(_HTML_CODE_START) + len(_HTML_CODE_END)

    def _html_code_description(self, string: str) -> str:
        return "{html_code_start}{string}{html_code_end}".format(
            html_code_start = self._HTML_CODE_START,
            string = string,
            html_code_end = self._HTML_CODE_END
        )

    def format_tag(self, record: logging.LogRecord) -> str:
        return self._TAG_FORMAT.format(
            level_name = record.levelname,
            timestamp = int(record.created)
        )

    def format(self, record: logging.LogRecord) -> str:
        return self._HEADER_FORMAT.format(
            emoticon = self._EMOTICONS[record.levelno],
            name = record.name,
            module = utils.html_escape(record.module),
            func_name = utils.html_escape(record.funcName),
            lineno = record.lineno,
            message = utils.html_escape(record.msg),
            description = (
                self._DESCRIPTION_FORMAT.format(
                    description = self._html_code_description(
                        string = utils.html_escape(
                            self.formatException(
                                ei = record.exc_info
                            )
                        )
                    )
                )
                if record.exc_info
                else
                ""
            )
        )

    def format_raw(self, record: logging.LogRecord) -> str:
        return self._RAW_FORMAT.format(
            level_name = record.levelname,
            name = record.name,
            module = record.module,
            func_name = record.funcName,
            lineno = record.lineno,
            message = record.msg,
            description = (
                "\n\n{description}".format(
                    description = self.formatException(
                        ei = record.exc_info
                    )
                )
                if record.exc_info
                else
                ""
            )
        )

    def format_by_fragments(self, record: logging.LogRecord) -> TEXT_FRAGMENTS_T:
        text: str = self.format(
            record = record
        )

        tag_text: str = "\n\n" + self.format_tag(
            record = record
        )

        if len(
            self.format_raw(
                record = record
            )
        ) + len(tag_text) <= self._MAX_TEXT_SIZE:
            return [text + tag_text]

        end_index: int = text.find(self._HTML_CODE_START)

        max_fragment_length: int = self._MAX_TEXT_SIZE - self._HTML_CODE_LENGTH - len(tag_text)

        if end_index == -1:
            return [text + tag_text]

        fragments: TEXT_FRAGMENTS_T = [
            text[:end_index] + tag_text,
            *[
                self._html_code_description(
                    string = text[index:index + max_fragment_length].replace(self._HTML_CODE_START, "").replace(self._HTML_CODE_END, "")
                ) + tag_text
                for index in range(end_index, len(text[end_index:]), max_fragment_length)
            ]
        ]

        return fragments
