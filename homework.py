"""Бот для проверки статусов в Практикуме и отправки уведомлений в Telegram."""

import logging
import sys
import time
import requests
from dotenv import load_dotenv, dotenv_values
from telebot import TeleBot, apihelper

# Импорт пользовательских исключений
from exceptions import EndpointError, ResponseFormatError, TelegramError


load_dotenv()
config = dotenv_values(".env")

PRACTICUM_TOKEN = config.get("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = config.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = config.get("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://praktikum.yandex.ru/api/user_api/homework_statuses/"
TIMEOUT = 10

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания."
}

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

    Если какая-либо переменная отсутствует, записывает ошибку в лог
    и завершает работу бота.
    """
    missing = []
    if not PRACTICUM_TOKEN:
        missing.append("PRACTICUM_TOKEN")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        error_msg = "Отсутствует обязательная переменная окружения: %s"
        logging.critical(error_msg, ", ".join(missing))
        sys.exit(1)


def send_message(bot, message):
    """Отправляет сообщение в Telegram.

    Args:
        bot (TeleBot): Экземпляр Telegram-бота.
        message (str): Текст сообщения.

    Raises:
        TelegramError: Если отправка сообщения не удалась.
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug("Бот отправил сообщение: %s", message)
    except apihelper.ApiException as e:
        logging.error("Ошибка отправки в Telegram: %s", e)
        raise TelegramError(f"Не удалось отправить сообщение: {e}") from e


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
    logging.info("Запрос к %s, параметры: %s", ENDPOINT, params)

    try:
        response = requests.get(
            ENDPOINT,
            headers={"Authorization": f"OAuth {PRACTICUM_TOKEN}"},
            params=params,
            timeout=TIMEOUT
        )
        if response.status_code != 200:
            raise EndpointError(response=response)
        return response.json()
    except requests.RequestException as e:
        raise EndpointError(message=f"Ошибка запроса: {e}") from e


def check_response(response):
    """Проверяет формат ответа API.

    Args:
        response (dict): Ответ API.

    Returns:
        list: Список работ из поля 'homeworks'.

    Raises:
        ResponseFormatError: Если ответ не соответствует ожидаемому формату.
    """
    if not isinstance(response, dict):
        raise ResponseFormatError(
            f"Ответ API не словарь, получен {type(response)}"
        )
    if "homeworks" not in response:
        raise ResponseFormatError("В ответе отсутствует ключ 'homeworks'")
    homeworks = response["homeworks"]
    if not isinstance(homeworks, list):
        raise ResponseFormatError(
            f"Поле 'homeworks' не список, получен {type(homeworks)}"
        )
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
    return f'Изменился статус работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
                timestamp = max(hw.get('updated_at', timestamp)
                                for hw in homeworks)
            else:
                logging.debug("Нет новых статусов")

            time.sleep(RETRY_PERIOD)

        except (EndpointError, ResponseFormatError, TelegramError,
                requests.RequestException) as error:
            error_msg = f'Сбой в работе программы: {error}'
            logging.error(error_msg)

            if str(error) != str(last_error):
                try:
                    send_message(bot, error_msg)
                except TelegramError:
                    pass
                last_error = error

            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
