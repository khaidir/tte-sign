"""Entry point: python -m app"""

from __future__ import annotations

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:create_app",
        host=settings.host,
        port=settings.port,
        workers=settings.web_concurrency,
        proxy_headers=True,
        server_header=False,
        log_config=None,
        factory=True,
    )


if __name__ == "__main__":
    main()
