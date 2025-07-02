"""
@file: tests/test_simple_demo.py
@description: Простой демонстрационный тест системы
@dependencies: pytest
@created: 2025-01-21
"""

import pytest
from unittest.mock import Mock


@pytest.mark.unit
def test_basic_functionality():
    """Простой тест для проверки базовой функциональности"""
    assert 1 + 1 == 2
    assert "hello" + " world" == "hello world"


@pytest.mark.unit
def test_mock_example():
    """Тест демонстрирующий работу с моками"""
    mock_service = Mock()
    mock_service.get_value.return_value = "test_value"
    
    result = mock_service.get_value()
    
    assert result == "test_value"
    mock_service.get_value.assert_called_once()


@pytest.mark.unit
def test_string_operations():
    """Тест строковых операций"""
    test_string = "Autoposter Bot Testing"
    
    assert test_string.lower() == "autoposter bot testing"
    assert test_string.replace("Testing", "Success") == "Autoposter Bot Success"
    assert len(test_string) == 22


@pytest.mark.unit
def test_list_operations():
    """Тест операций со списками"""
    test_list = [1, 2, 3, 4, 5]
    
    assert len(test_list) == 5
    assert sum(test_list) == 15
    assert max(test_list) == 5
    assert min(test_list) == 1


@pytest.mark.integration
def test_integration_example():
    """Пример интеграционного теста"""
    # Имитируем взаимодействие компонентов
    data = {"key": "value", "number": 42}
    
    processed_data = process_data(data)
    
    assert processed_data["key"] == "value"
    assert processed_data["number"] == 42
    assert "processed" in processed_data


def process_data(data):
    """Простая функция для обработки данных"""
    result = data.copy()
    result["processed"] = True
    return result 