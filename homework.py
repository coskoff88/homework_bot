from http import HTTPStatus
import os
import logging
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

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
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


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
        logging.error(f'Эндпоинт {ENDPOINT} недоступен: "{error}"')
        raise EndPointNotAvailableException(
            f'Эндпоинт {ENDPOINT} недоступен: "{error}"'
        )
    if response.status_code != HTTPStatus.OK:
        logging.error(
            f'Эндпоинт {ENDPOINT} вернул статус'
            f'{response.status_code}'
        )
        raise APIStatusCodeException(
            f'Эндпоинт {ENDPOINT} вернул статус'
            f'{response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    logging.debug('Начало проверки ответа API')
    if not isinstance(response, dict):
        logging.error('Ответ API имеет неверный тип')
        raise TypeError("Ответ API имеет неверный тип")
    if not ('homeworks' in response and "current_date" in response):
        logging.error('В ответе API отсутствуют ключи homeworks '
                      'или current_date')
        raise KeyError('В ответе API отсутствуют ключи homeworks '
                       'или current_date')
    if not isinstance(response['homeworks'], list):
        logging.error("Домашние работы в ответе API имеют неверный тип")
        raise TypeError("Домашние работы в ответе API имеют неверный тип")


def parse_status(homework):
    """Получение статуса домашней работы."""
    logging.debug('Начало получения статуса домашней работы')
    status = homework.get('status')
    if not status:
        logging.error('Статус домашней работы отсутствует')
        raise KeyError
    homework_name = homework.get('homework_name')
    if not homework_name:
        logging.error('Домашняя работа не имеет имени')
        raise KeyError
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        logging.error(
            f'Передан неизвестный статус домашней работы "{verdict}"'
        )
        raise KeyError
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
                homework_status = parse_status(homeworks[0])
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
