"""Бот для проверки статусов в Практикуме и отправки уведомлений в Telegram."""

import logging
import sys
import time

import requests
from dotenv import load_dotenv, dotenv_values
from telebot import TeleBot, apihelper

from exceptions import EndpointError, ResponseFormatError

load_dotenv()
config = dotenv_values(".env")

PRACTICUM_TOKEN = config.get("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = config.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = config.get("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
TIMEOUT = 10
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания."
}

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s,%(msecs)03d [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def check_tokens():
    """Проверяет наличие всех обязательных переменных окружения.

    Если какая‑либо переменная отсутствует, записывает ошибку в лог
    и завершает работу бота.
    """
    required_vars = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    missing = [var for var, value in required_vars.items() if not value]

    if missing:
        error_msg = (
            f"Отсутствует обязательная переменная окружения: "
            f"{', '.join(missing)}"
        )
        logging.critical(error_msg)
        raise ValueError(error_msg)


def send_message(bot, message):
    """Отправляет сообщение в Telegram.

    Args:
        bot (TeleBot): Экземпляр Telegram‑бота.
        message (str): Текст сообщения.

    Returns:
        bool: True, если сообщение отправлено успешно, False — в случае ошибки.
    """
    logging.info(f"Попытка отправки сообщения в Telegram: {message}")
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            timeout=TIMEOUT
        )
        logging.debug(f"Бот отправил сообщение: {message}")
        return True
    except (apihelper.ApiException, requests.RequestException) as e:
        logging.error(f"Ошибка отправки в Telegram: {e}")
        return False


def get_api_answer(timestamp):
    """Отправляет запрос к API Практикума.

    Args:
        timestamp (int): Метка времени для фильтрации работ.

    Returns:
        dict: JSON‑ответ API.

    Raises:
        EndpointError: Если запрос не удался или статус ответа ≠ 200.
    """
    params = {"from_date": timestamp}
    logging.info(f"Запрос к {ENDPOINT}, параметры: {params}")

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=TIMEOUT
        )
    except requests.RequestException as e:
        raise EndpointError(message=f"Ошибка запроса: {e}") from e

    if response.status_code != 200:
        raise EndpointError(response=response)

    return response.json()


def check_response(response):
    """Проверяет формат ответа API.

    Args:
        response (dict): Ответ API.

    Returns:
        list: Список работ из поля 'homeworks'.

    Raises:
        TypeError: Если ответ не соответствует ожидаемому формату.
    """
    if not isinstance(response, dict):
        raise TypeError(f"Ответ API не словарь, получен {type(response)}")
    if "homeworks" not in response:
        raise TypeError("В ответе отсутствует ключ 'homeworks'")
    homeworks = response["homeworks"]
    if not isinstance(homeworks, list):
        raise TypeError(
            f"Поле 'homeworks' не список, получен {type(homeworks)}")
    return homeworks


def parse_status(homework):
    """Формирует сообщение о статусе работы.

    Args:
        homework (dict): Данные о работе.

    Returns:
        str: Сообщение о статусе.

    Raises:
        ResponseFormatError: Если в работе отсутствуют обязательные поля
            или статус неизвестен.
    """
    required_keys = ["homework_name", "status"]
    for key in required_keys:
        if key not in homework:
            raise ResponseFormatError(f"В работе отсутствует ключ '{key}'")

    homework_name = homework["homework_name"]
    status = homework["status"]

    if status not in HOMEWORK_VERDICTS:
        raise ResponseFormatError(f"Неизвестный статус: {status}")

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
        bot = TeleBot(TELEGRAM_TOKEN)
        timestamp = int(time.time())
        last_error = None

        while True:
            try:
                response = get_api_answer(timestamp)
                homeworks = check_response(response)

                if homeworks:
                    homework = homeworks[0]
                    message = parse_status(homework)
                    if send_message(bot, message):
                        timestamp = response.get("current_date", timestamp)
                        last_error = None
                else:
                    logging.debug("Нет новых статусов")

            except Exception as error:
                error_msg = f'Сбой в работе программы: {error}'
                logging.error(error_msg)

                if str(error) != str(last_error):
                    send_message(bot, error_msg)
                    last_error = error

            finally:
                time.sleep(RETRY_PERIOD)

    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
