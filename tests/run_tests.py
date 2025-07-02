#!/usr/bin/env python3
"""
@file: tests/run_tests.py
@description: Скрипт для запуска всех тестов с отчетами
@dependencies: pytest, coverage
@created: 2025-01-21
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Запуск команды с выводом описания"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"⚠️ Предупреждения/Ошибки:\n{result.stderr}")
    
    if result.returncode != 0:
        print(f"❌ Команда завершилась с ошибкой (код: {result.returncode})")
        return False
    else:
        print(f"✅ {description} завершено успешно")
        return True


def install_dependencies():
    """Установка зависимостей для тестирования"""
    deps = [
        "pytest",
        "pytest-asyncio", 
        "pytest-cov",
        "pytest-html",
        "pytest-xdist",  # Для параллельного запуска
        "coverage[toml]",
        "aiosqlite",
        "aiogram-tests"
    ]
    
    cmd = f"{sys.executable} -m pip install {' '.join(deps)}"
    return run_command(cmd, "Установка зависимостей для тестирования")


def run_unit_tests():
    """Запуск модульных тестов"""
    cmd = "pytest tests/unit/ -v --tb=short -m unit"
    return run_command(cmd, "Запуск модульных тестов")


def run_integration_tests():
    """Запуск интеграционных тестов"""
    cmd = "pytest tests/integration/ -v --tb=short -m integration"
    return run_command(cmd, "Запуск интеграционных тестов")


def run_functional_tests():
    """Запуск функциональных тестов"""
    cmd = "pytest tests/functional/ -v --tb=short -m functional"
    return run_command(cmd, "Запуск функциональных тестов")


def run_all_tests_with_coverage():
    """Запуск всех тестов с измерением покрытия"""
    cmd = (
        "pytest tests/ -v --tb=short "
        "--cov=. "
        "--cov-report=html:tests/reports/coverage_html "
        "--cov-report=xml:tests/reports/coverage.xml "
        "--cov-report=term-missing "
        "--cov-config=tests/.coveragerc "
        "--html=tests/reports/report.html --self-contained-html"
    )
    return run_command(cmd, "Запуск всех тестов с покрытием кода")


def run_parallel_tests():
    """Запуск тестов в параллельном режиме"""
    import multiprocessing
    num_cores = multiprocessing.cpu_count()
    
    cmd = f"pytest tests/ -v -n {num_cores} --tb=short"
    return run_command(cmd, f"Запуск тестов в параллельном режиме ({num_cores} процессов)")


def run_specific_test_file(test_file):
    """Запуск конкретного файла тестов"""
    cmd = f"pytest {test_file} -v --tb=long"
    return run_command(cmd, f"Запуск тестов из файла {test_file}")


def run_tests_by_marker(marker):
    """Запуск тестов по маркеру"""
    cmd = f"pytest tests/ -v -m {marker} --tb=short"
    return run_command(cmd, f"Запуск тестов с маркером '{marker}'")


def generate_coverage_report():
    """Генерация отчета о покрытии"""
    cmd = "coverage html -d tests/reports/coverage_html"
    return run_command(cmd, "Генерация HTML отчета о покрытии кода")


def create_test_structure():
    """Создание структуры директорий для тестов"""
    dirs = [
        "tests/reports",
        "tests/unit",
        "tests/integration", 
        "tests/functional",
        "tests/fixtures"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✅ Структура директорий для тестов создана")


def create_coverage_config():
    """Создание файла конфигурации coverage"""
    config_content = """
[run]
source = .
omit = 
    tests/*
    venv/*
    __pycache__/*
    .git/*
    backups/*
    *.pyc
    */migrations/*
    setup.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if self.debug:
    if settings.DEBUG
    raise AssertionError
    raise NotImplementedError
    if 0:
    if __name__ == .__main__.:
    class .*\\bProtocol\\):
    @(abc\\.)?abstractmethod

[html]
directory = tests/reports/coverage_html
"""
    
    config_path = Path("tests/.coveragerc")
    config_path.write_text(config_content.strip())
    print("✅ Файл конфигурации coverage создан")


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Запуск тестов для Autoposter Bot")
    parser.add_argument(
        "--type", 
        choices=["unit", "integration", "functional", "all", "parallel"],
        default="all",
        help="Тип тестов для запуска"
    )
    parser.add_argument(
        "--marker", 
        help="Запуск тестов по конкретному маркеру"
    )
    parser.add_argument(
        "--file", 
        help="Запуск конкретного файла тестов"
    )
    parser.add_argument(
        "--install-deps", 
        action="store_true",
        help="Установить зависимости для тестирования"
    )
    parser.add_argument(
        "--coverage", 
        action="store_true",
        help="Включить измерение покрытия кода"
    )
    parser.add_argument(
        "--setup", 
        action="store_true",
        help="Создать структуру проекта для тестирования"
    )
    
    args = parser.parse_args()
    
    # Переходим в корневую директорию проекта
    os.chdir(Path(__file__).parent.parent)
    
    print("🧪 Autoposter Bot - Система тестирования")
    print("=" * 60)
    
    success = True
    
    if args.setup:
        create_test_structure()
        create_coverage_config()
        return
    
    if args.install_deps:
        success = install_dependencies()
        if not success:
            return
    
    if args.file:
        success = run_specific_test_file(args.file)
    elif args.marker:
        success = run_tests_by_marker(args.marker)
    elif args.type == "unit":
        success = run_unit_tests()
    elif args.type == "integration":
        success = run_integration_tests()
    elif args.type == "functional":
        success = run_functional_tests()
    elif args.type == "parallel":
        success = run_parallel_tests()
    elif args.type == "all":
        if args.coverage:
            success = run_all_tests_with_coverage()
        else:
            # Запускаем все типы тестов по очереди
            success &= run_unit_tests()
            success &= run_integration_tests()
            success &= run_functional_tests()
    
    print("\n" + "="*60)
    if success:
        print("🎉 Все тесты завершены успешно!")
        
        # Показываем расположение отчетов
        reports_dir = Path("tests/reports")
        if reports_dir.exists():
            print(f"\n📊 Отчеты доступны в: {reports_dir.absolute()}")
            
            html_report = reports_dir / "report.html"
            if html_report.exists():
                print(f"  • HTML отчет тестов: {html_report}")
                
            coverage_html = reports_dir / "coverage_html" / "index.html"
            if coverage_html.exists():
                print(f"  • HTML отчет покрытия: {coverage_html}")
    else:
        print("❌ Некоторые тесты завершились с ошибками!")
        sys.exit(1)


if __name__ == "__main__":
    main() 