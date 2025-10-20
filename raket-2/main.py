#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавление директории проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.config import config
from src.utils.logger import get_logger
from src.api.dexscreener import TokenScanner

logger = get_logger()

class TokenDataCollector:
    """
    Класс для сбора данных о токенах.
    """
    
    def __init__(self):
        """
        Инициализация коллектора данных.
        """
        logger.info(f"[SYSTEM] Запуск системы сбора данных о токенах v1.0")
        
        # Инициализация компонентов
        self.api = TokenScanner()
        
        # Путь для сохранения данных
        self.data_dir = Path("data/tokens")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def collect_token_data(self, max_age_hours: int = None) -> None:
        """
        Основной метод сбора данных о токенах.
        
        Args:
            max_age_hours: Максимальный возраст токена в часах
        """
        # Используем значение из конфига, если не указано явно
        if max_age_hours is None:
            max_age_hours = config.MAX_TOKEN_AGE_HOURS
        
        logger.info(f"[SYSTEM] Начало сбора данных о токенах (макс. возраст: {max_age_hours}ч)")
        
        try:
            # Получение токенов через API
            logger.info(f"[SYSTEM] Получение данных о токенах с DEXScreener")
            tokens = await self.api.find_rocket_tokens(max_age_hours=max_age_hours)
            logger.info(f"[SYSTEM] Получено {len(tokens)} токенов")
            
            # Сохранение данных
            await self.save_token_data(tokens)
            
        except Exception as e:
            logger.error(f"[SYSTEM] Ошибка при сборе данных: {str(e)}")
            raise
    
    async def save_token_data(self, tokens: list) -> None:
        """
        Сохраняет данные о токенах в JSON файл.
        
        Args:
            tokens: Список токенов для сохранения
        """
        logger.info(f"[SYSTEM] Сохранение данных о {len(tokens)} токенах")
        
        try:
            # Создаем структуру данных для сохранения
            data = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "total_tokens": len(tokens),
                    "config": {
                        "max_token_age_hours": config.MAX_TOKEN_AGE_HOURS,
                        "api_url": config.DEXSCREENER_API_URL
                    }
                },
                "tokens": tokens
            }
            
            # Формируем имя файла с текущей датой и временем
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tokens_data_{timestamp}.json"
            filepath = self.data_dir / filename
            
            # Сохраняем данные в JSON файл
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[SYSTEM] Данные сохранены в файл: {filepath}")
            
        except Exception as e:
            logger.error(f"[SYSTEM] Ошибка при сохранении данных: {str(e)}")
            raise
    
    async def run(self, args) -> None:
        """
        Запускает процесс сбора данных с указанными параметрами.
        
        Args:
            args: Аргументы командной строки
        """
        max_age = args.max_age if args.max_age is not None else config.MAX_TOKEN_AGE_HOURS
        logger.info(f"[SYSTEM] Установлен параметр макс. возраст: {max_age}ч")
        
        # Запуск сбора данных
        await self.collect_token_data(max_age_hours=max_age)
        
        logger.info(f"[SYSTEM] Завершение работы системы")


def parse_arguments():
    """
    Парсинг аргументов командной строки.
    
    Returns:
        argparse.Namespace: Объект с аргументами
    """
    parser = argparse.ArgumentParser(description='Система сбора данных о токенах')
    parser.add_argument('--max-age', type=int, help='Максимальный возраст токена (часы)')
    return parser.parse_args()


async def main():
    """
    Основная функция приложения.
    """
    args = parse_arguments()
    collector = TokenDataCollector()
    await collector.run(args)


if __name__ == "__main__":
    asyncio.run(main()) 