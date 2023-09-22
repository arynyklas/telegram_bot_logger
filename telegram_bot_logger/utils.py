from html import escape as _html_escape


def html_escape(string: str) -> str:
    return _html_escape(
        s = string,
        quote = False
    )
