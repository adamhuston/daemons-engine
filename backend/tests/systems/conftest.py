"""System test specific fixtures."""

import pytest

from app.engine.systems.bulk_service import BulkService
from app.engine.systems.file_manager import FileManager
from app.engine.systems.query_service import QueryService
from app.engine.systems.schema_registry import SchemaRegistry
from app.engine.systems.validation_service import ValidationService


@pytest.fixture
def file_manager(temp_world_data):
    """Create FileManager instance with temp world_data."""
    return FileManager(str(temp_world_data))


@pytest.fixture
def schema_registry(temp_world_data):
    """Create SchemaRegistry instance and load schemas."""
    registry = SchemaRegistry(str(temp_world_data))
    registry.load_all_schemas()
    return registry


@pytest.fixture
def validation_service(temp_world_data, file_manager, schema_registry):
    """Create ValidationService instance."""
    return ValidationService(
        world_data_path=str(temp_world_data),
        file_manager=file_manager,
        schema_registry=schema_registry,
    )


@pytest.fixture
def query_service(file_manager, temp_world_data):
    """Create QueryService instance."""
    return QueryService(file_manager=file_manager, world_data_path=str(temp_world_data))


@pytest.fixture
def bulk_service(file_manager, validation_service, schema_registry):
    """Create BulkService instance."""
    return BulkService(
        file_manager=file_manager,
        validation_service=validation_service,
        schema_registry=schema_registry,
    )
