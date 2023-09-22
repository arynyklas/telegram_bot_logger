import pathlib
import re
import sys

from setuptools import find_packages, setup


WORK_DIR = pathlib.Path(__file__).parent

MINIMAL_PY_VERSION = (3, 7)

if sys.version_info < MINIMAL_PY_VERSION:
    raise RuntimeError(
        "telegram_bot_logger works only with Python {}+".format(
            ".".join(
                map(str, MINIMAL_PY_VERSION)
            )
        )
    )


def get_version():
    return re.findall(
        pattern = r"^__version__ = \"([^']+)\"\r?$",
        string = (WORK_DIR / "telegram_bot_logger" / "__init__.py").read_text("utf-8"),
        flags = re.M
    )[0]


setup(
    name = "telegram_bot_logger",
    version = get_version(),
    packages = find_packages(
        exclude = [
            'examples.*'
        ]
    ),
    url = "https://github.com/arynyklas/telegram_bot_logger",
    author = "Aryn Yklas",
    requires_python = ">=3.7",
    author_email = "arynyklas@gmail.com",
    description = "Is a simple and synchronous logging handlers with sending logs to Telegram.",
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7"
    ],
    install_requires = [
        "httpx"
    ],
    include_package_data = False,
    keywords = [
        "telegram",
        "logger",
        "logging",
        "telegram_logger"
    ]
)
