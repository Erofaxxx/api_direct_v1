"""Генерация отчётов."""

from .pdf_generator import PDFReportGenerator, ReportSection, dataframe_to_report_table

__all__ = ["PDFReportGenerator", "ReportSection", "dataframe_to_report_table"]
