#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}🚀 Запуск анализатора токенов${NC}"

# Активация виртуального окружения
echo -e "${CYAN}🔧 Активация виртуального окружения...${NC}"
if [ -f "../raket-2/venv/bin/activate" ]; then
    source ../raket-2/venv/bin/activate
    echo -e "${GREEN}✓ Виртуальное окружение активировано${NC}"
else
    echo -e "${YELLOW}⚠️ Виртуальное окружение не найдено${NC}"
    echo -e "${YELLOW}Попытка запуска без виртуального окружения...${NC}"
fi

# Проверяем существование каталога reports
if [ -d "reports" ]; then
    echo -e "${CYAN}🗑️  Очистка каталога reports...${NC}"
    rm -rf reports/*
    echo -e "${GREEN}✅ Каталог reports очищен${NC}"
else
    echo -e "${CYAN}📁 Создание каталога reports...${NC}"
    mkdir reports
    echo -e "${GREEN}✅ Каталог reports создан${NC}"
fi

# Запускаем анализ
echo -e "${CYAN}📊 Запуск анализа...${NC}"
python3 src/main.py --analyze tokens/Final/final.json

echo -e "\n${GREEN}✨ Анализ завершен${NC}"
echo -e "${CYAN}📂 Результаты доступны в каталоге reports${NC}" 