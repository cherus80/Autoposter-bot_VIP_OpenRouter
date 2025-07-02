# 🧪 Система тестирования Autoposter Bot

Комплексная система тестирования для проверки всех компонентов бота и выявления ошибок.

## 📁 Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры и конфигурация
├── pytest.ini              # Настройки pytest
├── run_tests.py             # Скрипт запуска тестов
├── README.md               # Документация (этот файл)
├── .coveragerc             # Конфигурация coverage
├── unit/                   # Модульные тесты
│   ├── test_ai_service.py      # Тесты AI сервиса
│   ├── test_backup_service.py  # Тесты системы бэкапов
│   └── test_error_handler.py   # Тесты обработки ошибок
├── integration/            # Интеграционные тесты
│   └── test_database.py        # Тесты базы данных
├── functional/             # Функциональные тесты
│   └── test_post_creation.py   # Тесты создания постов
├── fixtures/               # Тестовые данные
│   └── test_content_plan.json  # Образец контент-плана
└── reports/                # Отчеты тестирования
    ├── coverage_html/          # HTML отчет покрытия
    ├── coverage.xml            # XML отчет покрытия
    └── report.html             # HTML отчет тестов
```

## 🎯 Типы тестов

### 🔧 Модульные тесты (Unit Tests)
- **Назначение**: Тестирование отдельных функций и методов
- **Покрытие**: AI сервис, системы бэкапов, обработка ошибок
- **Маркер**: `@pytest.mark.unit`
- **Быстрота**: Очень быстрые (секунды)

### 🔗 Интеграционные тесты (Integration Tests)  
- **Назначение**: Тестирование взаимодействия компонентов
- **Покрытие**: База данных, API интеграции, handlers
- **Маркер**: `@pytest.mark.integration`
- **Быстрота**: Средние (минуты)

### 🎭 Функциональные тесты (Functional Tests)
- **Назначение**: Тестирование пользовательских сценариев
- **Покрытие**: Полные workflow создания и публикации постов
- **Маркер**: `@pytest.mark.functional`
- **Быстрота**: Медленные (минуты)

## 🚀 Быстрый старт

### 1. Первоначальная настройка

```bash
# Создание структуры тестов
python tests/run_tests.py --setup

# Установка зависимостей
python tests/run_tests.py --install-deps
```

### 2. Запуск всех тестов

```bash
# Запуск всех тестов с покрытием кода
python tests/run_tests.py --type all --coverage

# Простой запуск всех тестов  
python tests/run_tests.py --type all
```

### 3. Запуск конкретных типов

```bash
# Только модульные тесты
python tests/run_tests.py --type unit

# Только интеграционные тесты
python tests/run_tests.py --type integration

# Только функциональные тесты
python tests/run_tests.py --type functional

# Параллельный запуск (быстрее)
python tests/run_tests.py --type parallel
```

## 🎯 Специальные команды

### Запуск по маркерам

```bash
# Тесты AI функций
python tests/run_tests.py --marker ai

# Тесты базы данных
python tests/run_tests.py --marker database

# Тесты системы бэкапов
python tests/run_tests.py --marker backup

# Тесты планировщика
python tests/run_tests.py --marker scheduler
```

### Запуск конкретных файлов

```bash
# Тест AI сервиса
python tests/run_tests.py --file tests/unit/test_ai_service.py

# Тест базы данных
python tests/run_tests.py --file tests/integration/test_database.py

# Тест создания постов
python tests/run_tests.py --file tests/functional/test_post_creation.py
```

### Прямые команды pytest

```bash
# Детальный вывод конкретного теста
pytest tests/unit/test_ai_service.py::TestAIService::test_generate_post_success -v -s

# Только тесты с определенным маркером
pytest -m "unit and ai" -v

# Тесты с покрытием
pytest --cov=services --cov-report=html

# Параллельный запуск
pytest -n auto
```

## 📊 Отчеты и анализ

### Отчеты покрытия кода
- **HTML отчет**: `tests/reports/coverage_html/index.html`
- **XML отчет**: `tests/reports/coverage.xml`
- **Консольный отчет**: выводится автоматически

### Отчеты тестирования
- **HTML отчет**: `tests/reports/report.html`
- **JUnit XML**: для CI/CD интеграции

### Анализ результатов

```bash
# Показать покрытие в консоли
coverage report

# Найти непокрытые строки
coverage report --show-missing

# Генерация HTML отчета
coverage html
```

## 🏗️ Создание новых тестов

### Модульный тест
```python
import pytest
from unittest.mock import AsyncMock
from services.my_service import MyService

@pytest.mark.unit
class TestMyService:
    @pytest.fixture
    def service(self):
        return MyService()
    
    @pytest.mark.asyncio
    async def test_my_function(self, service):
        result = await service.my_function("test")
        assert result == "expected"
```

### Интеграционный тест
```python
import pytest

@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_crud_operations(self, test_session):
        # Тест реальных операций с БД
        pass
```

### Функциональный тест
```python
import pytest

@pytest.mark.functional
class TestUserWorkflow:
    @pytest.mark.asyncio
    async def test_complete_post_creation(self, mock_bot, mock_message):
        # Тест полного пользовательского сценария
        pass
```

## 🔧 Настройка окружения

### Переменные окружения для тестов
```bash
export TESTING=true
export TEST_DB_URL="sqlite:///test.db"
export OPENAI_API_KEY="test_key"
export VK_TOKEN="test_token"
```

### Конфигурация pytest
```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
addopts = -ra -q --strict-markers
markers =
    unit: Unit tests
    integration: Integration tests
    functional: Functional tests
```

## 🐛 Отладка тестов

### Verbose режим
```bash
# Подробный вывод
pytest -v -s

# Очень подробный вывод
pytest -vv -s --tb=long

# Остановка на первой ошибке
pytest -x
```

### Дебаггинг
```bash
# Запуск с отладчиком
pytest --pdb

# Вывод print statements
pytest -s

# Логирование
pytest --log-cli-level=DEBUG
```

## 📈 Continuous Integration

### GitHub Actions пример
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - name: Install dependencies
        run: python tests/run_tests.py --install-deps
      - name: Run tests
        run: python tests/run_tests.py --type all --coverage
```

## 🎯 Цели покрытия

| Компонент | Цель покрытия | Текущее |
|-----------|---------------|---------|
| AI Service | 90%+ | - |
| Backup Service | 95%+ | - |
| Database | 85%+ | - |
| Handlers | 80%+ | - |
| Utils | 90%+ | - |

## 📋 Чек-лист перед релизом

- [ ] Все unit тесты проходят (100%)
- [ ] Все integration тесты проходят (100%)
- [ ] Все functional тесты проходят (100%)
- [ ] Покрытие кода > 80%
- [ ] Нет критических предупреждений
- [ ] Документация обновлена
- [ ] Performance тесты пройдены

## 🆘 Помощь и поддержка

### Частые проблемы

1. **ModuleNotFoundError**: Убедитесь, что запускаете тесты из корневой директории
2. **Database errors**: Проверьте права доступа к тестовой БД
3. **API errors**: Убедитесь в правильности мок-объектов

### Полезные команды

```bash
# Очистка кэша pytest
pytest --cache-clear

# Информация о фикстурах
pytest --fixtures

# Список всех тестов
pytest --collect-only

# Профилирование тестов
pytest --durations=10
```

---

**📞 Контакты**: Если возникли вопросы по тестированию, создайте issue или обратитесь к документации проекта. 