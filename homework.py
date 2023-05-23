import os
import logging
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import EndPointNotAvailableException, APIStatusCodeException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка обязательных переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    logging.debug('Начало отправки сообщения в Telegram')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except telegram.error.TelegramError as error:
        logging.error(f'Боту не удалось отправить сообщение: "{error}"')


def get_api_answer(timestamp):
    """Получение ответа API."""
    logging.debug('Начало получения ответа API')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except requests.RequestException as error:
        error_msg = f'Эндпоинт {ENDPOINT} недоступен: "{error}"'
        logging.error(error_msg)
        raise EndPointNotAvailableException(error_msg)
    if response.status_code != HTTPStatus.OK:
        error_msg = f'Эндпоинт {ENDPOINT} вернул статус {response.status_code}'
        logging.error(error_msg)
        raise APIStatusCodeException(error_msg)
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    logging.debug('Начало проверки ответа API')
    if not isinstance(response, dict):
        error_msg = 'Ответ API имеет неверный тип'
        logging.error(error_msg)
        raise TypeError(error_msg)
    for key in ('homeworks', "current_date"):
        if key not in response:
            error_msg = f'В ответе API отсутствует ключ {key}'
            logging.error(error_msg)
            raise KeyError(error_msg)
    if not isinstance(response['homeworks'], list):
        error_msg = "Домашние работы в ответе API имеют неверный тип"
        logging.error(error_msg)
        raise TypeError(error_msg)


def parse_status(homework):
    """Получение статуса домашней работы."""
    logging.debug('Начало получения статуса домашней работы')
    for key in ('status', 'homework_name'):
        if key not in homework:
            error_msg = f'В словаре homework отсутствует ключ {key}'
            logging.error(error_msg)
            raise KeyError(error_msg)
    status = homework['status']
    homework_name = homework['homework_name']
    if status not in HOMEWORK_VERDICTS:
        error_msg = f'Передан неизвестный статус домашней работы "{status}"'
        logging.error(error_msg)
        raise KeyError(error_msg)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            if not homeworks:
                logging.debug('Новых статусов не найдено')
            else:
                homework_status = parse_status(*homeworks)
                send_message(bot, homework_status)
                timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=logging.DEBUG,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    main()
