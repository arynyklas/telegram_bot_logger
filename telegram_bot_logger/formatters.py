from enum import Enum as _Enum, auto as _enum_auto

import logging

from . import utils

from typing import List, Union


TEXT_FRAGMENTS_T = List[str]


class FormatTypes(_Enum):
    TEXT = _enum_auto()
    DOCUMENT = _enum_auto()


class TelegramBaseFormatter(logging.Formatter):
    MAX_TEXT_SIZE: int = 4096
    PARSE_MODE: Union[str, None] = None

    def format_by_fragments(self, record: logging.LogRecord) -> TEXT_FRAGMENTS_T:
        raise NotImplementedError

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record

    # NOTE: if you want you can add this function to your own formatter, to get captions for documents
    # def get_record_tag(self, record: logging.LogRecord) -> str:
    #     raise NotImplementedError


class TelegramRawTextFormatter(TelegramBaseFormatter):
    pass


class TelegramHTMLTextFormatter(TelegramBaseFormatter):
    PARSE_MODE = "html"

    FORMAT: str = "{level_name} - {name} - ({module}).{func_name}({lineno}) - {message}{description}"
    TAG_FORMAT: str = "\n\n#log{timestamp} | {name} | {func_name}"

    HTML_CODE_START: str = "<code>"
    HTML_CODE_END: str = "</code>"

    HTML_CODE_LENGTH: int = len(HTML_CODE_START) + len(HTML_CODE_END)

    def _html_code(self, string: str) -> str:
        return "{html_code_start}{string}{html_code_end}".format(
            html_code_start = self.HTML_CODE_START,
            string = string,
            html_code_end = self.HTML_CODE_END
        )

    def get_record_tag(self, record: logging.LogRecord) -> str:
        return self.TAG_FORMAT.format(
            timestamp = int(record.created),
            name = record.name,
            func_name = record.funcName
        )

    def format(self, record: logging.LogRecord) -> str:
        return self.FORMAT.format(
            level_name = record.levelname,
            name = record.name,
            module = record.module,
            func_name = record.funcName,
            lineno = record.lineno,
            message = record.msg,
            description = (
                "\n\n{description}".format(
                    description = self._html_code(
                        string = utils.html_escape(
                            string = self.formatException(
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

    def format_by_fragments(self, record: logging.LogRecord) -> TEXT_FRAGMENTS_T:
        text: str = self.format(record)

        if len(text) <= self.MAX_TEXT_SIZE:
            return [text]

        start_index: int = 0

        end_index: int = text.find(self.HTML_CODE_START, start_index)

        tag_text: str = self.get_record_tag(record)

        max_fragment_length: int = self.MAX_TEXT_SIZE - self.HTML_CODE_LENGTH - len(tag_text)

        fragments: TEXT_FRAGMENTS_T = [
            text[start_index:end_index] + tag_text,
            *[
                self._html_code(
                    string = text[i:i + max_fragment_length].strip(self.HTML_CODE_START).strip(self.HTML_CODE_END)
                ) + tag_text
                for i in range(end_index, len(text[end_index:]), max_fragment_length)
            ]
        ]

        return fragments

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        record.module = utils.html_escape(
            string = record.module
        )

        record.funcName = utils.html_escape(
            string = record.funcName
        )

        return record
