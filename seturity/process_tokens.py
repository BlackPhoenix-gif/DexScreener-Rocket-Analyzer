import asyncio
import json
import os
from typing import List, Dict, Any
from free_analyzer import FreeTokenAnalyzer

class TokenProcessor:
    def __init__(self):
        self.analyzer = FreeTokenAnalyzer()
    
    async def process_tokens_file(self, input_file: str, output_file: str):
        """Обработка файла с токенами"""
        print(f"📂 Загрузка данных из {input_file}...")
        
        # Загрузка исходных данных
        tokens_data = self.load_tokens_data(input_file)
        if not tokens_data:
            print("❌ Не удалось загрузить данные")
            return
        
        # Фильтрация токенов (исключаем помеченные как scam)
        tokens_to_analyze = self.filter_tokens(tokens_data)
        print(f"🔍 Найдено {len(tokens_to_analyze)} токенов для анализа")
        
        # Извлечение адресов токенов
        token_addresses = []
        for token in tokens_to_analyze:
            # Проверяем различные форматы адресов
            address = None
            if isinstance(token, dict):
                # Новый формат с basic_info
                if 'basic_info' in token and 'address' in token['basic_info']:
                    address = token['basic_info']['address']
                # Старый формат
                elif 'address' in token:
                    address = token['address']
                elif 'token_address' in token:
                    address = token['token_address']
            
            if address:
                token_addresses.append(address)
        
        if not token_addresses:
            print("❌ Не найдено валидных адресов токенов")
            return
        
        # Убираем дубликаты
        unique_addresses = list(set(token_addresses))
        print(f"📊 Анализируем {len(unique_addresses)} уникальных токенов...")
        
        # Анализ токенов
        analyzed_tokens = []
        for i, token_address in enumerate(unique_addresses, 1):
            print(f"🔍 Анализ {i}/{len(unique_addresses)}: {token_address}")
            
            try:
                # Анализ токена
                report = await self.analyzer.analyze_token(token_address)
                
                # Добавление исходных данных
                original_data = next((t for t in tokens_to_analyze if 
                    (t.get('address') == token_address) or 
                    (t.get('token_address') == token_address) or
                    (t.get('basic_info', {}).get('address') == token_address)), {})
                report.external_checks['original_data'] = original_data
                
                analyzed_tokens.append(report.model_dump())
                
                print(f"✅ Завершен - Риск: {report.risk_assessment.risk_level.value}")
                
            except Exception as e:
                print(f"❌ Ошибка анализа {token_address}: {e}")
                continue
        
        # Сохранение результатов
        self.save_results(analyzed_tokens, output_file)
        print(f"💾 Результаты сохранены в {output_file}")
        
        # Генерация сводки
        self.generate_summary(analyzed_tokens)
    
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
                elif 'recommended_tokens' in data:
                    tokens = data['recommended_tokens']
                    # Добавляем информацию о risk_distribution
                    if 'risk_distribution' in data:
                        print(f"📊 Распределение рисков: {data['risk_distribution']}")
                    return tokens
                else:
                    return [data]
            elif isinstance(data, list):
                return data
            else:
                print(f"❌ Неизвестный формат данных в {file_path}")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка загрузки файла {file_path}: {e}")
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
                print(f"⏭️  Пропуск scam токена: {token.get('address', 'Unknown')}")
                continue
            
            filtered.append(token)
        
        return filtered
    
    def save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Сохранение результатов анализа"""
        try:
            output_data = {
                'analysis_timestamp': asyncio.get_event_loop().time(),
                'total_tokens_analyzed': len(results),
                'analysis_type': 'free',
                'results': results
            }
            
            # Создаем папку если не существует
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"❌ Ошибка сохранения результатов: {e}")
    
    def generate_summary(self, results: List[Dict[str, Any]]):
        """Генерация сводного отчета"""
        if not results:
            return
        
        print("\n" + "="*50)
        print("📊 СВОДНЫЙ ОТЧЕТ")
        print("="*50)
        
        # Статистика рисков
        risk_counts = {}
        total_time = 0
        verified_count = 0
        renounced_count = 0
        locked_count = 0
        
        for result in results:
            risk_level = result.get('risk_assessment', {}).get('risk_level', 'UNKNOWN')
            risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
            
            analysis_time = result.get('analysis_duration', 0)
            total_time += analysis_time
            
            if result.get('contract_analysis', {}).get('verified', False):
                verified_count += 1
            
            if result.get('ownership', {}).get('renounced', False):
                renounced_count += 1
            
            if result.get('distribution', {}).get('liquidity_locked', False):
                locked_count += 1
        
        print(f"📈 Всего проанализировано токенов: {len(results)}")
        print(f"⏱️  Среднее время анализа: {total_time/len(results):.2f}с")
        
        print(f"\n🎯 Распределение рисков:")
        for risk, count in risk_counts.items():
            percentage = (count / len(results)) * 100
            print(f"  {risk}: {count} токенов ({percentage:.1f}%)")
        
        print(f"\n🔧 Дополнительная статистика:")
        print(f"  • Верифицированных контрактов: {verified_count}/{len(results)}")
        print(f"  • Ренонсированных контрактов: {renounced_count}/{len(results)}")
        print(f"  • Заблокированной ликвидности: {locked_count}/{len(results)}")
        
        print(f"\n💡 Рекомендации:")
        if risk_counts.get('CRITICAL', 0) > 0:
            print(f"  ⚠️  Обнаружено {risk_counts['CRITICAL']} критически опасных токенов")
        if risk_counts.get('HIGH', 0) > 0:
            print(f"  ⚠️  Обнаружено {risk_counts['HIGH']} высокорисковых токенов")
        if renounced_count < len(results) * 0.5:
            print(f"  ⚠️  Менее 50% токенов имеют ренонсированных владельцев")
        if locked_count < len(results) * 0.3:
            print(f"  ⚠️  Менее 30% токенов имеют заблокированную ликвидность")

async def main():
    """Основная функция"""
    processor = TokenProcessor()
    
    # Пути к файлам
    input_file = "results/final_recommended_20250811_183555.json"
    output_file = "results/free_analysis_results.json"
    
    # Проверка существования входного файла
    if not os.path.exists(input_file):
        print(f"❌ Входной файл не найден: {input_file}")
        print("💡 Создайте файл с токенами в формате JSON")
        return
    
    # Обработка токенов
    await processor.process_tokens_file(input_file, output_file)
    
    print("\n🎉 Обработка завершена!")
    print(f"📁 Результаты сохранены в: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
