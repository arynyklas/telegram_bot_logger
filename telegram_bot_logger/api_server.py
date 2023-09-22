from dataclasses import dataclass

from typing import Any 


@dataclass(frozen=True)
class TelegramAPIServer:
    base: str

    def api_url(self, bot_token: str, method: str) -> str:
        return self.base.format(
            bot_token = bot_token,
            method = method
        )

    @classmethod
    def from_base(cls, base: str, **kwargs: Any) -> "TelegramAPIServer":
        base = base.rstrip("/")

        return cls(
            base=f"{base}/bot{{token}}/{{method}}",
            **kwargs,
        )


PRODUCTION_SERVER: TelegramAPIServer = TelegramAPIServer(
    base = "https://api.telegram.org/bot{bot_token}/{method}"
)
