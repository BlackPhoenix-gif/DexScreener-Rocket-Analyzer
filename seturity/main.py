import json
import asyncio
import os
from typing import List, Dict, Any
from token_analyzer import TokenAnalyzer
from models import TokenSecurityReport

class TokenSecurityProcessor:
    def __init__(self):
        self.analyzer = TokenAnalyzer()
    
    async def process_tokens_file(self, input_file: str, output_file: str):
        """Обработка файла с токенами"""
        print(f"Загрузка данных из {input_file}...")
        
        # Загрузка исходных данных
        tokens_data = self.load_tokens_data(input_file)
        if not tokens_data:
            print("Не удалось загрузить данные")
            return
        
        # Фильтрация токенов (исключаем помеченные как scam)
        tokens_to_analyze = self.filter_tokens(tokens_data)
        print(f"Найдено {len(tokens_to_analyze)} токенов для анализа")
        
        # Анализ токенов
        analyzed_tokens = []
        for i, token in enumerate(tokens_to_analyze):
            print(f"Анализ токена {i+1}/{len(tokens_to_analyze)}: {token.get('address', 'Unknown')}")
            
            try:
                # Получение адреса токена
                token_address = token.get('address', token.get('token_address', ''))
                if not token_address:
                    print(f"Пропуск токена без адреса: {token}")
                    continue
                
                # Анализ токена
                report = await self.analyzer.analyze_token(token_address)
                
                # Добавление исходных данных
                report.external_checks['original_data'] = token
                
                analyzed_tokens.append(report.model_dump())
                
                print(f"✅ Анализ завершен для {token_address}")
                print(f"   Риск: {report.risk_assessment.risk_level.value}")
                print(f"   Время: {report.analysis_duration:.2f}с")
                
            except Exception as e:
                print(f"❌ Ошибка анализа токена {token_address}: {e}")
                continue
        
        # Сохранение результатов
        self.save_results(analyzed_tokens, output_file)
        print(f"Результаты сохранены в {output_file}")
    
    def load_tokens_data(self, file_path: str) -> List[Dict[str, Any]]:
        """Загрузка данных токенов из файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Обработка различных форматов данных
            if isinstance(data, dict):
                if 'tokens' in data:
                    return data['tokens']
                elif 'results' in data:
                    return data['results']
                else:
                    return [data]
            elif isinstance(data, list):
                return data
            else:
                print(f"Неизвестный формат данных в {file_path}")
                return []
                
        except Exception as e:
            print(f"Ошибка загрузки файла {file_path}: {e}")
            return []
    
    def filter_tokens(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Фильтрация токенов (исключение помеченных как scam)"""
        filtered = []
        
        for token in tokens:
            # Проверяем различные поля, которые могут указывать на scam
            scam_indicators = [
                token.get('is_scam', False),
                token.get('scam', False),
                token.get('risk_level', '').lower() == 'scam',
                token.get('status', '').lower() == 'scam',
                token.get('type', '').lower() == 'scam'
            ]
            
            # Если токен помечен как scam, пропускаем его
            if any(scam_indicators):
                print(f"Пропуск scam токена: {token.get('address', 'Unknown')}")
                continue
            
            filtered.append(token)
        
        return filtered
    
    def save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Сохранение результатов анализа"""
        try:
            output_data = {
                'analysis_timestamp': asyncio.get_event_loop().time(),
                'total_tokens_analyzed': len(results),
                'results': results
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"Ошибка сохранения результатов: {e}")
    
    def generate_summary_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерация сводного отчета"""
        summary = {
            'total_tokens': len(results),
            'risk_distribution': {
                'LOW': 0,
                'MEDIUM': 0,
                'HIGH': 0,
                'CRITICAL': 0
            },
            'average_analysis_time': 0,
            'verified_contracts': 0,
            'renounced_contracts': 0,
            'liquidity_locked': 0
        }
        
        total_time = 0
        
        for result in results:
            # Распределение рисков
            risk_level = result.get('risk_assessment', {}).get('risk_level', 'UNKNOWN')
            summary['risk_distribution'][risk_level] += 1
            
            # Время анализа
            analysis_time = result.get('analysis_duration', 0)
            total_time += analysis_time
            
            # Верификация контрактов
            if result.get('contract_analysis', {}).get('verified', False):
                summary['verified_contracts'] += 1
            
            # Ренонс
            if result.get('ownership', {}).get('renounced', False):
                summary['renounced_contracts'] += 1
            
            # Ликвидность
            if result.get('distribution', {}).get('liquidity_locked', False):
                summary['liquidity_locked'] += 1
        
        if summary['total_tokens'] > 0:
            summary['average_analysis_time'] = total_time / summary['total_tokens']
        
        return summary

async def main():
    """Основная функция"""
    processor = TokenSecurityProcessor()
    
    # Пути к файлам
    input_file = "results/final_recommended_20250811_183555.json"
    output_file = "results/security_analysis_results.json"
    
    # Проверка существования входного файла
    if not os.path.exists(input_file):
        print(f"Входной файл не найден: {input_file}")
        print("Создаем тестовый файл...")
        
        # Создание тестового файла
        test_data = {
            "tokens": [
                {
                    "address": "0xA0b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C",
                    "name": "Test Token 1",
                    "symbol": "TEST1",
                    "is_scam": False
                },
                {
                    "address": "0xB1b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C",
                    "name": "Test Token 2", 
                    "symbol": "TEST2",
                    "is_scam": False
                }
            ]
        }
        
        os.makedirs("results", exist_ok=True)
        with open(input_file, 'w') as f:
            json.dump(test_data, f, indent=2)
    
    # Обработка токенов
    await processor.process_tokens_file(input_file, output_file)
    
    # Загрузка результатов для генерации сводки
    with open(output_file, 'r') as f:
        results_data = json.load(f)
    
    summary = processor.generate_summary_report(results_data['results'])
    
    print("\n" + "="*50)
    print("СВОДНЫЙ ОТЧЕТ")
    print("="*50)
    print(f"Всего проанализировано токенов: {summary['total_tokens']}")
    print(f"Среднее время анализа: {summary['average_analysis_time']:.2f}с")
    print("\nРаспределение рисков:")
    for risk, count in summary['risk_distribution'].items():
        percentage = (count / summary['total_tokens'] * 100) if summary['total_tokens'] > 0 else 0
        print(f"  {risk}: {count} ({percentage:.1f}%)")
    print(f"\nВерифицированных контрактов: {summary['verified_contracts']}")
    print(f"Ренонсированных контрактов: {summary['renounced_contracts']}")
    print(f"Заблокированной ликвидности: {summary['liquidity_locked']}")

if __name__ == "__main__":
    asyncio.run(main())
