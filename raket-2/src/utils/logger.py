import logging
import os
import sys
from datetime import datetime
import colorlog
from logging.handlers import RotatingFileHandler

class RaketLogger:
    """
    Класс для настройки и управления системой логирования.
    Обеспечивает форматированный вывод логов в консоль и файл.
    """
    
    def __init__(self, log_level=None, log_to_file=None, log_filename=None):
        """
        Инициализация логгера с указанными настройками.
        
        Args:
            log_level (str): Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file (bool): Флаг для записи логов в файл
            log_filename (str): Путь к файлу логов
        """
        # Определение настроек из переменных окружения или параметров
        self.log_level = log_level or os.environ.get('LOG_LEVEL', 'INFO').upper()
        self.log_to_file = log_to_file if log_to_file is not None else os.environ.get('LOG_TO_FILE', 'true').lower() == 'true'
        self.log_filename = log_filename or os.environ.get('LOG_FILENAME', 'logs/raket.log')
        
        # Создание директории для логов, если она не существует
        os.makedirs(os.path.dirname(self.log_filename), exist_ok=True)
        
        # Получение уровня логирования
        numeric_level = getattr(logging, self.log_level, None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Неверный уровень логирования: {self.log_level}')
        
        # Создание и настройка логгера
        self.logger = logging.getLogger('raket')
        self.logger.setLevel(numeric_level)
        self.logger.handlers = []  # Очистка хендлеров для предотвращения дублирования
        
        # Формат логирования
        log_format = '[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Настройка цветного логирования для консоли
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        
        console_formatter = colorlog.ColoredFormatter(
            fmt='%(log_color)s' + log_format,
            datefmt=date_format,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Настройка записи в файл, если требуется
        if self.log_to_file:
            file_handler = RotatingFileHandler(
                self.log_filename,
                maxBytes=10*1024*1024,  # 10 МБ
                backupCount=5
            )
            file_handler.setLevel(numeric_level)
            file_formatter = logging.Formatter(log_format, datefmt=date_format)
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def get_logger(self):
        """
        Возвращает настроенный логгер.
        
        Returns:
            logging.Logger: Настроенный логгер
        """
        return self.logger
    
    @staticmethod
    def setup():
        """
        Статический метод для быстрой настройки и получения логгера.
        
        Returns:
            logging.Logger: Настроенный логгер
        """
        return RaketLogger().get_logger()

# Создание глобального экземпляра логгера для использования во всем приложении
logger = RaketLogger.setup()

def get_logger():
    """
    Создает и настраивает логгер.
    
    Returns:
        logging.Logger: Настроенный логгер
    """
    logger = logging.getLogger("raket")
    logger.setLevel(logging.DEBUG)  # Изменяем уровень на DEBUG
    
    # Создаем форматтер для логов
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Изменяем уровень на DEBUG
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчик к логгеру
    logger.addHandler(console_handler)
    
    return logger

if __name__ == "__main__":
    # Пример использования логгера
    log = get_logger()
    log.debug("Это отладочное сообщение")
    log.info("Это информационное сообщение")
    log.warning("Это предупреждение")
    log.error("Это сообщение об ошибке")
    log.critical("Это критическая ошибка") 