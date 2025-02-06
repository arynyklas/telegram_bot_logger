import html


def html_escape(string: str) -> str:
    return html.escape(
        string,
        quote = False
    )
