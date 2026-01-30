"""
Расширенный анализатор данных для работы с большими таблицами.

Возможности:
- Анализ больших таблиц (chunking для Claude)
- Классификация текстовых данных (города, категории)
- Автоматическое определение типов столбцов
- Генерация статистики и визуализаций
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ColumnType(Enum):
    """Типы столбцов данных."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEXT = "text"
    DATE = "date"
    ID = "id"
    CITY = "city"
    REGION = "region"
    BOOLEAN = "boolean"


@dataclass
class ColumnInfo:
    """Информация о столбце."""
    name: str
    dtype: str
    col_type: ColumnType
    unique_count: int
    null_count: int
    sample_values: list[Any]
    statistics: dict[str, Any] | None = None


class DataAnalyzer:
    """
    Анализатор данных для подготовки к ML анализу.

    Функции:
    - Автоматическое определение типов столбцов
    - Классификация категориальных данных
    - Подготовка данных для Claude (chunking)
    - Генерация статистики
    """

    # Паттерны для определения типов столбцов
    CITY_KEYWORDS = ["город", "city", "город_", "city_", "location", "населённый"]
    REGION_KEYWORDS = ["регион", "region", "область", "край", "республика"]
    ID_KEYWORDS = ["id", "_id", "код", "code", "номер", "number"]
    DATE_KEYWORDS = ["date", "дата", "время", "time", "created", "updated"]

    def __init__(self, max_categories: int = 50, sample_size: int = 1000):
        """
        Args:
            max_categories: Максимум уникальных значений для категориального типа
            sample_size: Размер выборки для анализа
        """
        self.max_categories = max_categories
        self.sample_size = sample_size

    def analyze_dataframe(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Полный анализ DataFrame.

        Args:
            df: Исходный DataFrame

        Returns:
            Словарь с результатами анализа
        """
        logger.info(f"Анализ DataFrame: {len(df)} строк, {len(df.columns)} столбцов")

        # Анализ столбцов
        columns_info = {}
        for col in df.columns:
            columns_info[col] = self._analyze_column(df, col)

        # Общая статистика
        numeric_cols = [c for c, info in columns_info.items()
                       if info.col_type == ColumnType.NUMERIC]
        categorical_cols = [c for c, info in columns_info.items()
                          if info.col_type == ColumnType.CATEGORICAL]
        text_cols = [c for c, info in columns_info.items()
                    if info.col_type == ColumnType.TEXT]
        city_cols = [c for c, info in columns_info.items()
                   if info.col_type == ColumnType.CITY]
        region_cols = [c for c, info in columns_info.items()
                      if info.col_type == ColumnType.REGION]

        # Корреляции для числовых столбцов
        correlations = {}
        if len(numeric_cols) > 1:
            corr_matrix = df[numeric_cols].corr()
            correlations = corr_matrix.to_dict()

        # Группировки по категориям
        groupings = {}
        for cat_col in categorical_cols[:5]:  # Максимум 5 группировок
            if len(numeric_cols) > 0:
                groupings[cat_col] = df.groupby(cat_col)[numeric_cols[0]].agg(
                    ['mean', 'sum', 'count']
                ).head(20).to_dict()

        return {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": {name: self._column_info_to_dict(info)
                       for name, info in columns_info.items()},
            "column_types": {
                "numeric": numeric_cols,
                "categorical": categorical_cols,
                "text": text_cols,
                "city": city_cols,
                "region": region_cols,
            },
            "correlations": correlations,
            "groupings": groupings,
            "memory_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
        }

    def _analyze_column(self, df: pd.DataFrame, col: str) -> ColumnInfo:
        """Анализ отдельного столбца."""
        series = df[col]
        dtype = str(series.dtype)
        unique_count = series.nunique()
        null_count = series.isna().sum()

        # Определяем тип столбца
        col_type = self._detect_column_type(col, series, unique_count)

        # Примеры значений
        sample_values = series.dropna().head(10).tolist()

        # Статистика для числовых столбцов
        statistics = None
        if col_type == ColumnType.NUMERIC:
            statistics = {
                "min": float(series.min()) if not pd.isna(series.min()) else None,
                "max": float(series.max()) if not pd.isna(series.max()) else None,
                "mean": float(series.mean()) if not pd.isna(series.mean()) else None,
                "median": float(series.median()) if not pd.isna(series.median()) else None,
                "std": float(series.std()) if not pd.isna(series.std()) else None,
            }

        return ColumnInfo(
            name=col,
            dtype=dtype,
            col_type=col_type,
            unique_count=unique_count,
            null_count=null_count,
            sample_values=sample_values,
            statistics=statistics,
        )

    def _detect_column_type(
        self,
        col_name: str,
        series: pd.Series,
        unique_count: int,
    ) -> ColumnType:
        """Определение типа столбца."""
        col_lower = col_name.lower()

        # Проверка по имени
        if any(kw in col_lower for kw in self.ID_KEYWORDS):
            return ColumnType.ID

        if any(kw in col_lower for kw in self.CITY_KEYWORDS):
            return ColumnType.CITY

        if any(kw in col_lower for kw in self.REGION_KEYWORDS):
            return ColumnType.REGION

        if any(kw in col_lower for kw in self.DATE_KEYWORDS):
            return ColumnType.DATE

        # Проверка по типу данных
        if pd.api.types.is_numeric_dtype(series):
            return ColumnType.NUMERIC

        if pd.api.types.is_bool_dtype(series):
            return ColumnType.BOOLEAN

        if pd.api.types.is_datetime64_any_dtype(series):
            return ColumnType.DATE

        # Текст vs категория
        if unique_count <= self.max_categories:
            return ColumnType.CATEGORICAL

        return ColumnType.TEXT

    def _column_info_to_dict(self, info: ColumnInfo) -> dict[str, Any]:
        """Конвертация ColumnInfo в словарь."""
        return {
            "dtype": info.dtype,
            "type": info.col_type.value,
            "unique_count": info.unique_count,
            "null_count": info.null_count,
            "sample_values": info.sample_values[:5],
            "statistics": info.statistics,
        }

    def prepare_for_claude(
        self,
        df: pd.DataFrame,
        max_rows: int = 100,
        max_chars: int = 50000,
    ) -> list[dict[str, Any]]:
        """
        Подготовка данных для анализа Claude.

        Для больших таблиц разбивает на чанки.

        Args:
            df: DataFrame для анализа
            max_rows: Максимум строк в одном чанке
            max_chars: Максимум символов в чанке

        Returns:
            Список чанков для отправки в Claude
        """
        chunks = []

        # Базовый анализ всегда включается
        analysis = self.analyze_dataframe(df)
        chunks.append({
            "type": "metadata",
            "content": json.dumps(analysis, ensure_ascii=False, default=str),
        })

        # Если таблица маленькая, отправляем всю
        if len(df) <= max_rows:
            chunks.append({
                "type": "full_data",
                "content": df.to_json(orient="records", force_ascii=False),
            })
            return chunks

        # Для больших таблиц - стратифицированная выборка
        # 1. Начало таблицы
        chunks.append({
            "type": "sample_head",
            "description": f"Первые {min(30, len(df))} строк",
            "content": df.head(30).to_json(orient="records", force_ascii=False),
        })

        # 2. Случайная выборка
        sample_size = min(50, len(df))
        sample = df.sample(n=sample_size, random_state=42)
        chunks.append({
            "type": "sample_random",
            "description": f"Случайная выборка {sample_size} строк",
            "content": sample.to_json(orient="records", force_ascii=False),
        })

        # 3. Агрегированные данные по категориям
        categorical_cols = [
            col for col, info in analysis["columns"].items()
            if info["type"] in ("categorical", "city", "region")
        ]

        numeric_cols = analysis["column_types"]["numeric"]

        if categorical_cols and numeric_cols:
            for cat_col in categorical_cols[:3]:
                agg_data = df.groupby(cat_col)[numeric_cols].agg(
                    ["mean", "sum", "count"]
                ).head(30)
                chunks.append({
                    "type": "aggregation",
                    "group_by": cat_col,
                    "content": agg_data.to_json(force_ascii=False),
                })

        return chunks

    def classify_text_column(
        self,
        df: pd.DataFrame,
        column: str,
        categories: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Классификация текстового столбца по категориям.

        Args:
            df: DataFrame
            column: Имя столбца для классификации
            categories: Список категорий (если None - автоопределение)

        Returns:
            DataFrame с добавленным столбцом категорий
        """
        result = df.copy()

        if categories is None:
            # Автоопределение категорий
            unique_values = df[column].dropna().unique()
            if len(unique_values) <= self.max_categories:
                categories = list(unique_values)
            else:
                # Берём топ по частоте
                categories = df[column].value_counts().head(self.max_categories).index.tolist()

        # Создаём маппинг
        category_map = {cat: i for i, cat in enumerate(categories)}
        result[f"{column}_category_id"] = result[column].map(category_map)
        result[f"{column}_category_id"] = result[f"{column}_category_id"].fillna(-1).astype(int)

        return result

    def get_city_statistics(self, df: pd.DataFrame, city_column: str) -> dict[str, Any]:
        """
        Статистика по городам.

        Args:
            df: DataFrame
            city_column: Имя столбца с городами

        Returns:
            Статистика по городам
        """
        city_stats = df[city_column].value_counts()

        return {
            "total_cities": city_stats.count(),
            "top_cities": city_stats.head(20).to_dict(),
            "city_distribution": {
                "top_10_percent": city_stats.head(int(len(city_stats) * 0.1)).sum() / len(df) * 100,
                "top_20_percent": city_stats.head(int(len(city_stats) * 0.2)).sum() / len(df) * 100,
            }
        }


class ChartGenerator:
    """
    Генератор графиков для отчётов.
    """

    def __init__(self, output_dir: str = "reports/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_bar_chart(
        self,
        data: dict[str, float],
        title: str,
        xlabel: str,
        ylabel: str,
        filename: str,
    ) -> str:
        """Генерация столбчатой диаграммы."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        plt.figure(figsize=(12, 6))
        plt.bar(list(data.keys())[:20], list(data.values())[:20])
        plt.title(title, fontsize=14)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        filepath = self.output_dir / f"{filename}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_pie_chart(
        self,
        data: dict[str, float],
        title: str,
        filename: str,
    ) -> str:
        """Генерация круговой диаграммы."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Берём топ-10, остальное в "Другие"
        sorted_data = dict(sorted(data.items(), key=lambda x: x[1], reverse=True))
        top_data = dict(list(sorted_data.items())[:10])
        others = sum(list(sorted_data.values())[10:])
        if others > 0:
            top_data["Другие"] = others

        plt.figure(figsize=(10, 8))
        plt.pie(
            top_data.values(),
            labels=top_data.keys(),
            autopct='%1.1f%%',
            startangle=90
        )
        plt.title(title, fontsize=14)
        plt.tight_layout()

        filepath = self.output_dir / f"{filename}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_line_chart(
        self,
        x_data: list,
        y_data: list,
        title: str,
        xlabel: str,
        ylabel: str,
        filename: str,
    ) -> str:
        """Генерация линейного графика."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        plt.figure(figsize=(12, 6))
        plt.plot(x_data, y_data, marker='o', linewidth=2, markersize=4)
        plt.title(title, fontsize=14)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        filepath = self.output_dir / f"{filename}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_heatmap(
        self,
        df: pd.DataFrame,
        title: str,
        filename: str,
    ) -> str:
        """Генерация тепловой карты корреляций."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.figure(figsize=(12, 10))
        sns.heatmap(
            df,
            annot=True,
            cmap='coolwarm',
            center=0,
            fmt='.2f',
            square=True,
        )
        plt.title(title, fontsize=14)
        plt.tight_layout()

        filepath = self.output_dir / f"{filename}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_histogram(
        self,
        data: list[float],
        title: str,
        xlabel: str,
        filename: str,
        bins: int = 30,
    ) -> str:
        """Генерация гистограммы."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 6))
        plt.hist(data, bins=bins, edgecolor='black', alpha=0.7)
        plt.title(title, fontsize=14)
        plt.xlabel(xlabel)
        plt.ylabel("Частота")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        filepath = self.output_dir / f"{filename}.png"
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)
