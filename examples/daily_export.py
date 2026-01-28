#!/usr/bin/env python3
"""
Пример: Ежедневная выгрузка данных из Яндекс Директа.

Этот скрипт демонстрирует:
1. Подключение к API Яндекс Директа
2. Выгрузку данных о кампаниях и статистике
3. Сохранение данных для ML анализа

Запуск:
    python -m examples.daily_export

Для работы требуется:
    - Заполнить .env файл с YANDEX_DIRECT_TOKEN
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from yandex_direct_api.app import YandexDirectApp


def main():
    """
    Выполняет ежедневную выгрузку данных.

    Последовательность операций:
    1. Инициализация клиента API
    2. Campaigns.get - получение списка кампаний
    3. Reports API - получение статистики по кампаниям
    4. AdGroups.get - получение групп объявлений
    5. Keywords.get - получение ключевых фраз
    6. Reports API - получение статистики по фразам
    7. Сохранение данных в JSON и CSV

    Все запросы выполняются с интервалом 200мс (5 req/sec limit).
    При ошибках применяется экспоненциальная задержка.
    """
    print("Запуск ежедневной выгрузки данных из Яндекс Директа")
    print("-" * 50)

    with YandexDirectApp(output_dir="data/exports") as app:
        results = app.run_daily_export()

        print("\nРезультаты:")
        print(f"  Кампаний: {len(results['campaigns'])}")
        print(f"  Записей статистики: {len(results['statistics'])}")
        print(f"  Статистика по фразам: {len(results['keywords_stats'])}")

        if results['errors']:
            print(f"\nОшибки: {len(results['errors'])}")
            for err in results['errors']:
                print(f"  - {err['type']}: {err['message']}")


if __name__ == "__main__":
    main()
