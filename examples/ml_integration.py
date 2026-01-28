#!/usr/bin/env python3
"""
Пример: Интеграция с ML моделью для оптимизации ставок.

Этот скрипт демонстрирует:
1. Загрузку данных из Яндекс Директа
2. Слияние с данными CRM
3. Применение ML рекомендаций по ставкам

Использование:
    python -m examples.ml_integration
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from yandex_direct_api.app import YandexDirectApp


def load_crm_data() -> pd.DataFrame:
    """
    Загружает данные из CRM.

    В реальном приложении здесь будет подключение к CRM.
    """
    # Пример структуры данных CRM
    return pd.DataFrame({
        "keyword_id": [1001, 1002, 1003],
        "conversions": [10, 5, 15],
        "revenue": [50000, 25000, 75000],
        "margin": [0.3, 0.25, 0.35],
    })


def merge_data(
    direct_stats: pd.DataFrame,
    crm_data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Слияние данных из Директа и CRM.

    Args:
        direct_stats: Статистика из Яндекс Директа
        crm_data: Данные из CRM

    Returns:
        Объединенный датафрейм
    """
    # Переименовываем колонку для слияния
    if "CriterionId" in direct_stats.columns:
        direct_stats = direct_stats.rename(columns={"CriterionId": "keyword_id"})

    # Слияние по keyword_id
    merged = direct_stats.merge(
        crm_data,
        on="keyword_id",
        how="left",
    )

    return merged


def calculate_bid_recommendations(data: pd.DataFrame) -> list[dict]:
    """
    Рассчитывает рекомендации по ставкам.

    Простая эвристика (в реальности здесь будет ML модель):
    - Если ROI > 30% и CTR > 2%, увеличить ставку на 10%
    - Если ROI < 10%, уменьшить ставку на 20%

    Args:
        data: Объединенные данные

    Returns:
        Список рекомендаций по ставкам
    """
    recommendations = []

    for _, row in data.iterrows():
        if pd.isna(row.get("keyword_id")):
            continue

        current_bid = float(row.get("AvgCpc", 0) or 0)
        if current_bid == 0:
            continue

        # Расчет ROI
        cost = float(row.get("Cost", 0) or 0)
        revenue = float(row.get("revenue", 0) or 0)

        if cost > 0:
            roi = (revenue - cost) / cost
        else:
            roi = 0

        ctr = float(row.get("Ctr", 0) or 0)

        # Применяем правила
        new_bid = current_bid

        if roi > 0.3 and ctr > 2.0:
            new_bid = current_bid * 1.1  # +10%
        elif roi < 0.1 and cost > 0:
            new_bid = current_bid * 0.8  # -20%

        if new_bid != current_bid:
            recommendations.append({
                "keyword_id": int(row["keyword_id"]),
                "current_bid": current_bid,
                "new_bid": round(new_bid, 2),
                "roi": round(roi, 3),
                "ctr": round(ctr, 2),
            })

    return recommendations


def main():
    """Основной процесс ML интеграции."""
    print("Интеграция с ML для оптимизации ставок")
    print("-" * 50)

    # 1. Получаем данные из Яндекс Директа
    print("\n1. Получение данных из Яндекс Директа...")

    with YandexDirectApp() as app:
        results = app.run_daily_export()

    direct_stats = pd.DataFrame(results.get("keywords_stats", []))

    if direct_stats.empty:
        print("Нет данных статистики. Завершение.")
        return

    print(f"   Получено записей: {len(direct_stats)}")

    # 2. Загружаем данные CRM
    print("\n2. Загрузка данных из CRM...")
    crm_data = load_crm_data()
    print(f"   Записей CRM: {len(crm_data)}")

    # 3. Объединяем данные
    print("\n3. Слияние данных...")
    merged_data = merge_data(direct_stats, crm_data)
    print(f"   Объединенных записей: {len(merged_data)}")

    # Сохраняем для ML анализа
    merged_data.to_csv("data/merged_for_ml.csv", index=False)
    print("   Сохранено в data/merged_for_ml.csv")

    # 4. Рассчитываем рекомендации
    print("\n4. Расчет рекомендаций по ставкам...")
    recommendations = calculate_bid_recommendations(merged_data)
    print(f"   Рекомендаций: {len(recommendations)}")

    if recommendations:
        print("\n   Примеры рекомендаций:")
        for rec in recommendations[:5]:
            print(
                f"   - Фраза {rec['keyword_id']}: "
                f"{rec['current_bid']:.2f} -> {rec['new_bid']:.2f} руб "
                f"(ROI: {rec['roi']:.1%}, CTR: {rec['ctr']:.2f}%)"
            )

        # 5. Применяем рекомендации (опционально, по запросу)
        apply = input("\nПрименить рекомендации? (y/n): ")
        if apply.lower() == "y":
            print("\n5. Применение рекомендаций...")
            with YandexDirectApp() as app:
                result = app.apply_bid_recommendations(recommendations)
                print(f"   Успешно обновлено: {result['success']}")
                if result['errors']:
                    print(f"   Ошибок: {len(result['errors'])}")


if __name__ == "__main__":
    main()
