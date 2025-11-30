"""
Bulk Operations Service for CMS - Phase 12.5

Provides batch import/export functionality for YAML content files.
Enables:
- Bulk import with pre-validation and atomic operations
- ZIP archive export with manifest
- Batch validation of multiple files
"""

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .file_manager import FileManager
from .schema_registry import SchemaRegistry
from .validation_service import ValidationResult, ValidationService


@dataclass
class BulkImportRequest:
    """Request for bulk import operation"""

    files: Dict[str, str]  # {file_path: content}
    validate_only: bool = False
    rollback_on_error: bool = True
    overwrite_existing: bool = True


@dataclass
class FileImportResult:
    """Result of importing a single file"""

    file_path: str
    success: bool
    written: bool = False
    validation_result: Optional[ValidationResult] = None
    error: Optional[str] = None
    checksum: Optional[str] = None


@dataclass
class BulkImportResponse:
    """Response from bulk import operation"""

    success: bool
    total_files: int
    files_validated: int
    files_written: int
    files_failed: int
    results: List[FileImportResult] = field(default_factory=list)
    rolled_back: bool = False
    error: Optional[str] = None


@dataclass
class BulkExportRequest:
    """Request for bulk export operation"""

    content_types: Optional[List[str]] = None  # None = all types
    include_schema_files: bool = False
    file_paths: Optional[List[str]] = None  # Specific files only


@dataclass
class BulkExportResponse:
    """Response from bulk export operation"""

    success: bool
    zip_path: str  # Path to generated ZIP file
    total_files: int
    manifest: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class BatchValidationRequest:
    """Request for batch validation"""

    files: Dict[str, str]  # {file_path: content}


@dataclass
class BatchValidationResponse:
    """Response from batch validation"""

    success: bool
    total_files: int
    valid_files: int
    invalid_files: int
    results: List[ValidationResult] = field(default_factory=list)


class BulkService:
    """
    Manages bulk import/export operations for YAML content.

    Features:
    - Pre-validation before writing any files
    - Atomic operations with rollback support
    - ZIP archive export with manifest
    - Batch validation
    """

    def __init__(
        self,
        file_manager: FileManager,
        validation_service: ValidationService,
        schema_registry: SchemaRegistry,
    ):
        self.file_manager = file_manager
        self.validation_service = validation_service
        self.schema_registry = schema_registry

        # Track import operations for rollback
        self._import_backups: Dict[
            str, Optional[str]
        ] = {}  # {file_path: original_content | None}

    async def bulk_import(self, request: BulkImportRequest) -> BulkImportResponse:
        """
        Import multiple YAML files with validation.

        Process:
        1. Validate all files first
        2. If validate_only, return results
        3. If any validation fails and rollback_on_error, abort
        4. Write all files atomically
        5. If any write fails and rollback_on_error, restore backups

        Args:
            request: BulkImportRequest with files to import

        Returns:
            BulkImportResponse with detailed results
        """
        results: List[FileImportResult] = []
        self._import_backups.clear()

        try:
            # Phase 1: Validate all files
            validation_results = await self._validate_all_files(request.files)

            # Build results from validation
            for file_path, validation_result in validation_results.items():
                results.append(
                    FileImportResult(
                        file_path=file_path,
                        success=validation_result.valid,
                        validation_result=validation_result,
                    )
                )

            # Count validation outcomes
            valid_count = sum(1 for r in results if r.success)
            failed_count = len(results) - valid_count

            # If validate_only, return here
            if request.validate_only:
                return BulkImportResponse(
                    success=True,
                    total_files=len(results),
                    files_validated=len(results),
                    files_written=0,
                    files_failed=failed_count,
                    results=results,
                )

            # If rollback_on_error and any validation failed, abort
            if request.rollback_on_error and failed_count > 0:
                return BulkImportResponse(
                    success=False,
                    total_files=len(results),
                    files_validated=len(results),
                    files_written=0,
                    files_failed=failed_count,
                    results=results,
                    error=f"{failed_count} file(s) failed validation. No files written.",
                )

            # Phase 2: Backup existing files (for rollback)
            if request.rollback_on_error:
                await self._backup_existing_files(request.files.keys())

            # Phase 3: Write valid files
            written_count = 0
            write_errors: List[str] = []

            for result in results:
                if not result.success:
                    # Skip files that failed validation
                    continue

                try:
                    # Write the file
                    content = request.files[result.file_path]
                    success, checksum, errors = await self.file_manager.write_file(
                        result.file_path, content
                    )
                    if success:
                        result.written = True
                        result.checksum = checksum
                        written_count += 1
                    else:
                        result.success = False
                        result.error = f"Write failed: {', '.join(errors)}"
                        write_errors.append(result.file_path)
                except Exception as e:
                    result.success = False
                    result.error = f"Write failed: {str(e)}"
                    write_errors.append(result.file_path)

            # If write errors occurred and rollback requested, restore backups
            if write_errors and request.rollback_on_error:
                await self._rollback_imports()
                return BulkImportResponse(
                    success=False,
                    total_files=len(results),
                    files_validated=len(results),
                    files_written=0,
                    files_failed=len(results),
                    results=results,
                    rolled_back=True,
                    error=f"Write failed for {len(write_errors)} file(s). All changes rolled back.",
                )

            # Success
            return BulkImportResponse(
                success=(failed_count == 0 and len(write_errors) == 0),
                total_files=len(results),
                files_validated=len(results),
                files_written=written_count,
                files_failed=failed_count + len(write_errors),
                results=results,
            )

        except Exception as e:
            # Unexpected error - rollback if requested
            if request.rollback_on_error and self._import_backups:
                await self._rollback_imports()
                rolled_back = True
            else:
                rolled_back = False

            return BulkImportResponse(
                success=False,
                total_files=len(request.files),
                files_validated=len(results),
                files_written=0,
                files_failed=len(request.files),
                results=results,
                rolled_back=rolled_back,
                error=f"Bulk import failed: {str(e)}",
            )
        finally:
            self._import_backups.clear()

    async def bulk_export(self, request: BulkExportRequest) -> BulkExportResponse:
        """
        Export multiple YAML files to a ZIP archive.

        Process:
        1. Determine which files to export
        2. Create temporary directory
        3. Copy files to temp directory
        4. Generate manifest.json
        5. Create ZIP archive
        6. Return path to ZIP

        Args:
            request: BulkExportRequest with export criteria

        Returns:
            BulkExportResponse with ZIP path and manifest
        """
        try:
            # Determine files to export
            if request.file_paths:
                # Specific files requested
                file_paths = request.file_paths
            else:
                # List files by content type
                # FileManager.list_files only supports single content_type filter
                content_type_str = (
                    request.content_types[0]
                    if request.content_types and len(request.content_types) == 1
                    else None
                )
                all_files = await self.file_manager.list_files(
                    content_type_filter=content_type_str,
                    include_schema_files=request.include_schema_files,
                )
                file_paths = [f.file_path for f in all_files]

            if not file_paths:
                return BulkExportResponse(
                    success=False,
                    zip_path="",
                    total_files=0,
                    manifest={},
                    error="No files matched export criteria",
                )

            # Create temporary directory for staging
            temp_dir = Path(tempfile.mkdtemp(prefix="bulk_export_"))

            try:
                # Copy files to temp directory
                exported_files: List[Dict[str, Any]] = []

                for file_path in file_paths:
                    try:
                        # Read file
                        file_content = await self.file_manager.read_file(file_path)

                        # Create directory structure in temp
                        dest_file = temp_dir / file_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)

                        # Write file
                        dest_file.write_text(file_content.content, encoding="utf-8")

                        # Track exported file
                        content_type = self.file_manager._get_content_type(file_path)
                        exported_files.append(
                            {
                                "path": file_path,
                                "size": file_content.size_bytes,
                                "checksum": file_content.checksum,
                                "last_modified": file_content.last_modified.isoformat(),
                                "content_type": content_type,
                            }
                        )
                    except Exception as e:
                        # Log error but continue with other files
                        print(f"Warning: Failed to export {file_path}: {e}")

                # Generate manifest
                manifest = {
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "total_files": len(exported_files),
                    "content_types": request.content_types or ["all"],
                    "include_schema_files": request.include_schema_files,
                    "files": exported_files,
                }

                # Write manifest to temp directory
                manifest_file = temp_dir / "manifest.json"
                manifest_file.write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )

                # Create ZIP archive
                zip_filename = (
                    f"content_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
                )
                zip_path = temp_dir.parent / zip_filename

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    # Add all files from temp directory
                    for file in temp_dir.rglob("*"):
                        if file.is_file():
                            arcname = file.relative_to(temp_dir)
                            zipf.write(file, arcname)

                return BulkExportResponse(
                    success=True,
                    zip_path=str(zip_path),
                    total_files=len(exported_files),
                    manifest=manifest,
                )

            finally:
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            return BulkExportResponse(
                success=False,
                zip_path="",
                total_files=0,
                manifest={},
                error=f"Export failed: {str(e)}",
            )

    async def batch_validate(
        self, request: BatchValidationRequest
    ) -> BatchValidationResponse:
        """
        Validate multiple YAML files without writing them.

        Args:
            request: BatchValidationRequest with files to validate

        Returns:
            BatchValidationResponse with validation results
        """
        try:
            # Validate all files
            validation_results = await self._validate_all_files(request.files)

            # Convert to list
            results = list(validation_results.values())

            # Count outcomes
            valid_count = sum(1 for r in results if r.valid)
            invalid_count = len(results) - valid_count

            return BatchValidationResponse(
                success=True,
                total_files=len(results),
                valid_files=valid_count,
                invalid_files=invalid_count,
                results=results,
            )

        except Exception as e:
            return BatchValidationResponse(
                success=False,
                total_files=len(request.files),
                valid_files=0,
                invalid_files=len(request.files),
                error=f"Batch validation failed: {str(e)}",
            )

    # --- Helper Methods ---

    async def _validate_all_files(
        self, files: Dict[str, str]
    ) -> Dict[str, ValidationResult]:
        """
        Validate all files in parallel.

        Args:
            files: {file_path: content}

        Returns:
            {file_path: ValidationResult}
        """
        # Build result dict
        validation_results = {}

        for file_path, content in files.items():
            try:
                # Determine content type from file path
                content_type = self.file_manager._get_content_type(file_path)

                # Validate using validate_full (syntax + schema + references)
                result = await self.validation_service.validate_full(
                    yaml_content=content, content_type=content_type
                )
                # Set file path in result
                result.file_path = file_path
                validation_results[file_path] = result

            except Exception as e:
                # Validation raised exception - treat as invalid
                validation_results[file_path] = ValidationResult(
                    valid=False,
                    content_type="unknown",
                    file_path=file_path,
                    errors=[
                        {
                            "severity": "error",
                            "message": f"Validation exception: {str(e)}",
                            "error_type": "system",
                        }
                    ],
                )

        return validation_results

    async def _backup_existing_files(self, file_paths: List[str]) -> None:
        """
        Backup existing files for rollback.

        Args:
            file_paths: Files to backup
        """
        for file_path in file_paths:
            try:
                # Read existing content (if file exists)
                file_content = await self.file_manager.read_file(file_path)
                self._import_backups[file_path] = file_content.content
            except FileNotFoundError:
                # File doesn't exist yet - mark as new
                self._import_backups[file_path] = None
            except Exception as e:
                # Backup failed - log but continue
                print(f"Warning: Failed to backup {file_path}: {e}")
                self._import_backups[file_path] = None

    async def _rollback_imports(self) -> None:
        """
        Rollback all imported files to their backup state.
        """
        for file_path, backup_content in self._import_backups.items():
            try:
                if backup_content is None:
                    # File was new - delete it
                    await self.file_manager.delete_file(file_path)
                else:
                    # File existed - restore backup
                    await self.file_manager.write_file(file_path, backup_content)
            except Exception as e:
                # Rollback failed - log error
                print(f"Error: Failed to rollback {file_path}: {e}")
