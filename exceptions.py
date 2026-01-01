"""
Модуль для пользовательских исключений бота.

Содержит классы для обработки ошибок API и некорректных ответов.
"""


class EndpointError(Exception):
    """Возникает при недоступности эндпоинта API или HTTP‑ошибках."""

    def __init__(self, message=None, response=None):
        """
        Инициализация исключения.

        Параметры:
        - message (str): пользовательское сообщение (опционально).
        - response (requests.Response): объект ответа для анализа (опционально)
        """
        if message is None and response is not None:
            message = (
                f"Эндпоинт {response.url} недоступен. "
                f"Код ответа: {response.status_code}, тело: {response.text}"
            )
        elif message is None:
            message = "Ошибка доступа к эндпоинту API."
        super().__init__(message)


class ResponseFormatError(Exception):
    """Возникает при нарушении формата ответа API (нет ключей, ошибка типа)."""


class TelegramError(Exception):
    """Возникает при ошибках отправки сообщений в Telegram."""
