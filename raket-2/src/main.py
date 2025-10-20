import os
import asyncio
from typing import List
from src.api.dexscreener import DexScreenerAPI
from src.filter.rocket_filter import RocketFilter
from src.reporting.report_generator import ReportGenerator
from src.analysis.contract_analyzer import ContractAnalyzer
from src.models.token import Token
from src.utils.logger import get_logger

logger = get_logger()

class RaketSystem:
    """
    Основной класс системы поиска и анализа высокодоходных токенов
    """
    
    def __init__(self):
        """
        Инициализация системы
        """
        self.api = DexScreenerAPI()
        self.filter = RocketFilter()
        self.report_generator = ReportGenerator()
        self.contract_analyzer = ContractAnalyzer()
        
        logger.info("[SYSTEM] Запуск системы поиска ракет v1.0")
    
    async def find_rockets(self, max_age_hours: float = 72.0) -> List[Token]:
        """
        Поиск потенциальных ракет
        
        Args:
            max_age_hours: Максимальный возраст токена в часах
            
        Returns:
            List[Token]: Список найденных ракет
        """
        logger.info(f"[SYSTEM] Установлен параметр макс. возраст: {max_age_hours}ч")
        
        # Получение токенов
        logger.info("[SYSTEM] Начало сканирования токенов")
        tokens = await self.api.find_rocket_tokens(max_age_hours)
        logger.info(f"[SYSTEM] Получено {len(tokens)} токенов")
        
        # Фильтрация токенов
        logger.info("[SYSTEM] Фильтрация потенциальных ракет")
        rockets = self.filter.filter_rockets(tokens)
        logger.info(f"[SYSTEM] Найдено {len(rockets)} потенциальных ракет")
        
        # Анализ контрактов
        logger.info("[SYSTEM] Анализ контрактов ракет")
        for rocket in rockets:
            try:
                risk_info = self.contract_analyzer.analyze_contract(rocket.address, rocket.chain_id)
                rocket.update_risk_info(
                    risk_level=risk_info['risk_level'],
                    risks=risk_info['risks'],
                    warnings=risk_info['warnings'],
                    contract_info=risk_info['info']
                )
                logger.info(f"[SYSTEM] Проанализирован контракт {rocket.symbol}: {risk_info['risk_level']}")
            except Exception as e:
                logger.error(f"[SYSTEM] Ошибка при анализе контракта {rocket.symbol}: {str(e)}")
        
        # Сортировка ракет
        logger.info("[SYSTEM] Сортировка ракет по потенциалу")
        rockets = self.filter.sort_rockets(rockets)
        
        return rockets
    
    async def generate_report(self, rockets: List[Token], report_format: str = 'all') -> List[str]:
        """
        Генерация отчета о найденных ракетах
        
        Args:
            rockets: Список ракет для отчета
            report_format: Формат отчета ('json', 'csv', 'html' или 'all')
            
        Returns:
            List[str]: Список путей к сгенерированным отчетам
        """
        return self.report_generator.generate_reports(rockets, report_format)
    
    def print_top_rockets(self, rockets: List[Token], top_n: int = 5):
        """
        Вывод топ-N ракет в консоль
        
        Args:
            rockets: Список ракет
            top_n: Количество ракет для вывода
        """
        logger.info("[SYSTEM] Топ-5 потенциальных ракет:")
        for i, rocket in enumerate(rockets[:top_n], 1):
            logger.info(f"{i}. {rocket.symbol} ({rocket.name}): +{rocket.max_price_change_24h:.1f}% (24ч), "
                       f"ликв. ${rocket.total_liquidity_usd:.1f}, возраст {rocket.age_hours:.1f}ч")

async def main():
    """
    Основная функция запуска системы
    """
    try:
        # Инициализация системы
        system = RaketSystem()
        
        # Поиск ракет
        rockets = await system.find_rockets()
        
        # Генерация отчетов
        report_files = await system.generate_report(rockets)
        
        # Вывод путей к отчетам
        for report_file in report_files:
            logger.info(f"[SYSTEM] Отчет ({os.path.splitext(report_file)[1][1:]}): {report_file}")
        
        # Вывод топ-5 ракет
        system.print_top_rockets(rockets)
        
        logger.info("[SYSTEM] Завершение работы системы")
        
    except Exception as e:
        logger.error(f"[SYSTEM] Критическая ошибка: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 