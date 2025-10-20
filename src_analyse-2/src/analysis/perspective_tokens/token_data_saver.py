import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

class TokenDataSaver:
    """
    Класс для сохранения данных о перспективных токенах в JSON формате
    """
    
    def __init__(self, output_dir: Path):
        """
        Инициализация класса
        
        Args:
            output_dir: Директория для сохранения результатов
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем директорию для отчетов
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        # Удаляем старый finalResult.json если он существует
        self.final_result_path = self.report_dir / "finalResult.json"
        if self.final_result_path.exists():
            self.final_result_path.unlink()
    
    def save_tokens_data(self, tokens: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        """
        Сохраняет данные о токенах и конфигурацию в JSON файл
        
        Args:
            tokens: Список токенов с их данными
            config: Конфигурация, использованная при анализе
            
        Returns:
            str: Путь к сохраненному файлу
        """
        # Создаем структуру данных для сохранения
        data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_tokens": len(tokens),
                "analysis_config": config
            },
            "tokens": tokens
        }
        
        # Формируем имя файла с текущей датой и временем
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"perspective_tokens_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # Сохраняем данные в JSON файл
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Копируем файл в директорию report и переименовываем в finalResult.json
        shutil.copy2(filepath, self.final_result_path)
        
        return str(filepath) 