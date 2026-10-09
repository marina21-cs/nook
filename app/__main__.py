import uvicorn

from app.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.port,
        workers=1,
        proxy_headers=False,
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
