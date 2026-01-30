"""
Генератор PDF отчётов с использованием LaTeX.

Возможности:
- Генерация профессиональных PDF отчётов
- Встраивание графиков и таблиц
- Поддержка русского языка
- Автоматическое форматирование
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """Секция отчёта."""
    title: str
    content: str
    charts: list[str] | None = None
    tables: list[dict] | None = None


class PDFReportGenerator:
    """
    Генератор PDF отчётов с LaTeX.

    Требования:
    - texlive-full (Ubuntu: sudo apt install texlive-full)
    - texlive-lang-cyrillic (для русского языка)
    """

    LATEX_TEMPLATE = r"""
\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T2A]{fontenc}
\usepackage[russian]{babel}
\usepackage{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{fancyhdr}
\usepackage{lastpage}
\usepackage{float}

\geometry{margin=2.5cm}

% Цвета
\definecolor{primary}{RGB}{41, 128, 185}
\definecolor{secondary}{RGB}{52, 73, 94}
\definecolor{success}{RGB}{39, 174, 96}
\definecolor{warning}{RGB}{241, 196, 15}
\definecolor{danger}{RGB}{231, 76, 60}

% Стиль заголовков
\usepackage{titlesec}
\titleformat{\section}{\Large\bfseries\color{primary}}{\thesection}{1em}{}
\titleformat{\subsection}{\large\bfseries\color{secondary}}{\thesubsection}{1em}{}

% Колонтитулы
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\color{secondary}{{REPORT_TITLE}}}
\fancyhead[R]{\small\color{secondary}\today}
\fancyfoot[C]{\small\color{secondary}Страница \thepage\ из \pageref{LastPage}}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}

\begin{document}

% Титульная страница
\begin{titlepage}
\centering
\vspace*{3cm}

{\Huge\bfseries\color{primary} {REPORT_TITLE} \par}
\vspace{1cm}
{\Large\color{secondary} Аналитический отчёт \par}
\vspace{2cm}

{\large Дата формирования: \today \par}
\vspace{0.5cm}
{\large Период анализа: {DATE_RANGE} \par}

\vfill

{\large\color{secondary} Сформировано автоматически \par}
{\large\color{secondary} Мультиагентная система анализа данных \par}

\end{titlepage}

\tableofcontents
\newpage

{CONTENT}

\end{document}
"""

    TABLE_TEMPLATE = r"""
\begin{table}[H]
\centering
\caption{{TABLE_CAPTION}}
\begin{tabular}{{TABLE_COLUMNS}}
\toprule
{TABLE_HEADER}
\midrule
{TABLE_ROWS}
\bottomrule
\end{tabular}
\end{table}
"""

    FIGURE_TEMPLATE = r"""
\begin{figure}[H]
\centering
\includegraphics[width={WIDTH}\textwidth]{{IMAGE_PATH}}
\caption{{CAPTION}}
\end{figure}
"""

    def __init__(self, output_dir: str = "reports/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = None

    def generate_report(
        self,
        title: str,
        sections: list[ReportSection],
        date_range: str = "",
        output_filename: str | None = None,
    ) -> str:
        """
        Генерация PDF отчёта.

        Args:
            title: Заголовок отчёта
            sections: Список секций отчёта
            date_range: Период анализа
            output_filename: Имя выходного файла

        Returns:
            Путь к сгенерированному PDF файлу
        """
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"report_{timestamp}"

        logger.info(f"Генерация отчёта: {title}")

        # Создаём временную директорию
        self.temp_dir = Path(tempfile.mkdtemp())

        try:
            # Формируем контент
            content = self._generate_content(sections)

            # Заполняем шаблон
            latex_content = self.LATEX_TEMPLATE
            latex_content = latex_content.replace("{REPORT_TITLE}", self._escape_latex(title))
            latex_content = latex_content.replace("{DATE_RANGE}", self._escape_latex(date_range))
            latex_content = latex_content.replace("{CONTENT}", content)

            # Сохраняем LaTeX файл
            tex_file = self.temp_dir / "report.tex"
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(latex_content)

            # Компилируем PDF
            pdf_path = self._compile_latex(tex_file, output_filename)

            logger.info(f"Отчёт сгенерирован: {pdf_path}")
            return pdf_path

        finally:
            # Очищаем временные файлы
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_content(self, sections: list[ReportSection]) -> str:
        """Генерация контента из секций."""
        content_parts = []

        for section in sections:
            parts = []

            # Заголовок секции
            parts.append(f"\\section{{{self._escape_latex(section.title)}}}")

            # Текстовый контент
            if section.content:
                parts.append(self._escape_latex(section.content))
                parts.append("")

            # Графики
            if section.charts:
                for i, chart_path in enumerate(section.charts):
                    # Копируем изображение во временную директорию
                    if Path(chart_path).exists():
                        dest = self.temp_dir / f"chart_{len(content_parts)}_{i}.png"
                        shutil.copy(chart_path, dest)

                        figure = self.FIGURE_TEMPLATE
                        figure = figure.replace("{WIDTH}", "0.9")
                        figure = figure.replace("{IMAGE_PATH}", dest.name)
                        figure = figure.replace("{CAPTION}", f"График {i+1}")
                        parts.append(figure)

            # Таблицы
            if section.tables:
                for table_data in section.tables:
                    table_latex = self._generate_table(table_data)
                    parts.append(table_latex)

            content_parts.append("\n".join(parts))

        return "\n\n".join(content_parts)

    def _generate_table(self, table_data: dict) -> str:
        """Генерация LaTeX таблицы."""
        caption = table_data.get("caption", "Таблица")
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])

        if not headers or not rows:
            return ""

        # Формат колонок
        columns = "|" + "|".join(["l"] * len(headers)) + "|"

        # Заголовок
        header_row = " & ".join([f"\\textbf{{{self._escape_latex(h)}}}" for h in headers]) + " \\\\"

        # Строки данных
        row_lines = []
        for row in rows[:50]:  # Максимум 50 строк
            cells = [self._escape_latex(str(cell)[:50]) for cell in row]
            row_lines.append(" & ".join(cells) + " \\\\")

        table = self.TABLE_TEMPLATE
        table = table.replace("{TABLE_CAPTION}", self._escape_latex(caption))
        table = table.replace("{TABLE_COLUMNS}", columns)
        table = table.replace("{TABLE_HEADER}", header_row)
        table = table.replace("{TABLE_ROWS}", "\n".join(row_lines))

        return table

    def _escape_latex(self, text: str) -> str:
        """Экранирование специальных символов LaTeX."""
        if not isinstance(text, str):
            text = str(text)

        replacements = [
            ("\\", "\\textbackslash{}"),
            ("&", "\\&"),
            ("%", "\\%"),
            ("$", "\\$"),
            ("#", "\\#"),
            ("_", "\\_"),
            ("{", "\\{"),
            ("}", "\\}"),
            ("~", "\\textasciitilde{}"),
            ("^", "\\textasciicircum{}"),
        ]

        for old, new in replacements:
            text = text.replace(old, new)

        return text

    def _compile_latex(self, tex_file: Path, output_name: str) -> str:
        """Компиляция LaTeX в PDF."""
        # Запускаем pdflatex дважды для корректных ссылок
        for _ in range(2):
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-output-directory", str(self.temp_dir),
                    str(tex_file),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                logger.warning(f"pdflatex warning: {result.stderr[:500]}")

        # Копируем PDF в выходную директорию
        pdf_source = self.temp_dir / "report.pdf"
        pdf_dest = self.output_dir / f"{output_name}.pdf"

        if pdf_source.exists():
            shutil.copy(pdf_source, pdf_dest)
            return str(pdf_dest)
        else:
            raise RuntimeError("PDF не был сгенерирован. Проверьте установку LaTeX.")

    def generate_from_analysis(
        self,
        analysis_result: dict[str, Any],
        charts: list[str],
        title: str = "Аналитический отчёт",
    ) -> str:
        """
        Генерация отчёта из результатов анализа.

        Args:
            analysis_result: Результаты ML анализа
            charts: Пути к графикам
            title: Заголовок отчёта

        Returns:
            Путь к PDF файлу
        """
        sections = []

        # Секция: Резюме
        if "summary" in analysis_result:
            sections.append(ReportSection(
                title="Резюме",
                content=analysis_result["summary"],
            ))

        # Секция: Ключевые показатели
        if "key_insights" in analysis_result:
            insights = analysis_result["key_insights"]
            content = "\n".join([f"• {insight}" for insight in insights])
            sections.append(ReportSection(
                title="Ключевые выводы",
                content=content,
            ))

        # Секция: Топ кампании
        if "top_campaigns" in analysis_result:
            sections.append(ReportSection(
                title="Лучшие кампании",
                content="",
                tables=[{
                    "caption": "Топ кампании по эффективности",
                    "headers": ["Кампания", "Показатель"],
                    "rows": [[c, "—"] for c in analysis_result["top_campaigns"][:10]],
                }],
            ))

        # Секция: Графики
        if charts:
            sections.append(ReportSection(
                title="Визуализация данных",
                content="",
                charts=charts,
            ))

        # Секция: Рекомендации
        if "recommendations" in analysis_result:
            recs = analysis_result["recommendations"]
            content = "\n".join([f"{i+1}. {rec}" for i, rec in enumerate(recs)])
            sections.append(ReportSection(
                title="Рекомендации",
                content=content,
            ))

        # Секция: Рекомендации по ставкам
        if "bid_recommendations" in analysis_result:
            bid_recs = analysis_result["bid_recommendations"]
            if bid_recs:
                rows = [
                    [
                        str(r.get("keyword_id", "")),
                        f"{r.get('current_bid', 0):.2f}",
                        f"{r.get('new_bid', 0):.2f}",
                        r.get("reason", ""),
                    ]
                    for r in bid_recs[:20]
                ]
                sections.append(ReportSection(
                    title="Рекомендации по ставкам",
                    content="",
                    tables=[{
                        "caption": "Рекомендуемые изменения ставок",
                        "headers": ["ID фразы", "Текущая ставка", "Новая ставка", "Причина"],
                        "rows": rows,
                    }],
                ))

        return self.generate_report(
            title=title,
            sections=sections,
            date_range=analysis_result.get("date_range", ""),
        )


def dataframe_to_report_table(
    df: pd.DataFrame,
    caption: str = "Таблица",
    max_rows: int = 50,
) -> dict:
    """
    Конвертация DataFrame в формат таблицы для отчёта.

    Args:
        df: DataFrame
        caption: Заголовок таблицы
        max_rows: Максимум строк

    Returns:
        Словарь с данными таблицы
    """
    return {
        "caption": caption,
        "headers": list(df.columns),
        "rows": df.head(max_rows).values.tolist(),
    }
