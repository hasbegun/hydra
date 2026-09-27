"""
Service for managing custom garak probes.

Metadata is stored in the SQLite database (custom_probes table) with
fallback to the legacy metadata.json file when the DB is unavailable.
Probe .py files always live on disk.
"""
import ast
import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import importlib.util
import sys

from models.schemas import (
    CustomProbe,
    CustomProbeCreateRequest,
    CustomProbeValidateRequest,
    CustomProbeValidationResponse,
    ValidationError,
    CustomProbeListResponse,
    CustomProbeGetResponse,
)

logger = logging.getLogger(__name__)


from database.session import db_available as _db_available


class CustomProbeService:
    """Service for managing custom probes"""

    def __init__(self):
        # Custom probes directory
        self.custom_probes_dir = Path.home() / ".garak" / "custom_probes"
        self.custom_probes_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file
        self.metadata_file = self.custom_probes_dir / "metadata.json"
        self._ensure_metadata_file()

        # Initialize __init__.py
        self._ensure_init_file()

    def _ensure_metadata_file(self):
        """Ensure metadata file exists"""
        if not self.metadata_file.exists():
            self.metadata_file.write_text(json.dumps({"probes": {}}, indent=2))

    def _ensure_init_file(self):
        """Ensure __init__.py exists in custom probes directory"""
        init_file = self.custom_probes_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Custom garak probes"""\n')

    def _read_metadata(self) -> Dict[str, Any]:
        """Read metadata — DB-backed with file fallback."""
        if _db_available():
            try:
                from database.session import get_db
                from database.models import CustomProbeRow
                with get_db() as db:
                    rows = db.query(CustomProbeRow).all()
                    probes = {row.name: row.to_dict() for row in rows}
                    return {"probes": probes}
            except Exception as e:
                logger.warning(f"DB read failed for probes, falling back to file: {e}")
        # Fallback: file-based
        try:
            return json.loads(self.metadata_file.read_text())
        except Exception:
            return {"probes": {}}

    def _write_metadata(self, metadata: Dict[str, Any]):
        """Write metadata to file (fallback only — DB writes happen in CRUD methods)."""
        self.metadata_file.write_text(json.dumps(metadata, indent=2))

    def _is_valid_python_identifier(self, name: str) -> bool:
        """Check if name is a valid Python identifier"""
        return name.isidentifier() and not name.startswith('_')

    def validate_code(self, request: CustomProbeValidateRequest) -> CustomProbeValidationResponse:
        """Validate probe code"""
        code = request.code
        errors = []
        warnings = []
        probe_info = {}

        # 1. Check syntax
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return CustomProbeValidationResponse(
                valid=False,
                errors=[ValidationError(
                    line=e.lineno,
                    column=e.offset,
                    message=str(e.msg),
                    error_type="syntax"
                )]
            )

        # 2. Check for imports
        has_garak_import = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    if node.module and 'garak' in node.module:
                        has_garak_import = True
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if 'garak' in alias.name:
                            has_garak_import = True

        if not has_garak_import:
            warnings.append("No garak imports found. Make sure to import garak.probes.base")

        # 3. Find probe class
        probe_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from something that looks like a probe
                if node.bases:
                    probe_classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'docstring': ast.get_docstring(node),
                        'has_bases': len(node.bases) > 0
                    })

        if not probe_classes:
            errors.append(ValidationError(
                line=None,
                column=None,
                message="No class definition found. Probe must be a class.",
                error_type="structure"
            ))
        else:
            probe_info['classes'] = probe_classes

            # Extract probe attributes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    if target.id == 'prompts':
                                        probe_info['has_prompts'] = True
                                    elif target.id == 'goal':
                                        probe_info['has_goal'] = True
                                    elif target.id == 'primary_detector':
                                        probe_info['has_primary_detector'] = True
                                    elif target.id == 'tags':
                                        probe_info['has_tags'] = True

        # 4. Check for dangerous imports/operations
        dangerous_modules = ['os', 'subprocess', 'shutil', 'socket']
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    if node.module in dangerous_modules:
                        warnings.append(f"Warning: Import of potentially dangerous module '{node.module}'")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in dangerous_modules:
                            warnings.append(f"Warning: Import of potentially dangerous module '{alias.name}'")

        # Determine if valid
        is_valid = len(errors) == 0

        return CustomProbeValidationResponse(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            probe_info=probe_info if is_valid else None
        )

    def create_probe(self, request: CustomProbeCreateRequest) -> CustomProbe:
        """Create a new custom probe"""
        # Validate name
        if not self._is_valid_python_identifier(request.name):
            raise ValueError(f"Invalid probe name: {request.name}. Must be a valid Python identifier.")

        # Validate code
        validation = self.validate_code(CustomProbeValidateRequest(code=request.code))
        if not validation.valid:
            error_messages = [f"Line {e.line}: {e.message}" if e.line else e.message for e in validation.errors]
            raise ValueError(f"Invalid probe code: {'; '.join(error_messages)}")

        # Generate filename (lowercase with underscores)
        filename = re.sub(r'(?<!^)(?=[A-Z])', '_', request.name).lower()
        file_path = self.custom_probes_dir / f"{filename}.py"

        now = datetime.utcnow().isoformat()
        goal = None
        if validation.probe_info:
            classes = validation.probe_info.get('classes', [])
            if classes:
                goal = classes[0].get('docstring')

        probe_metadata = {
            "name": request.name,
            "file_path": str(file_path),
            "description": request.description,
            "goal": goal,
            "created_at": now,
            "updated_at": now,
        }

        if _db_available():
            try:
                from database.session import get_db
                from database.models import CustomProbeRow
                with get_db() as db:
                    existing = db.query(CustomProbeRow).filter_by(name=request.name).first()
                    if existing:
                        raise ValueError(f"Probe '{request.name}' already exists")
                    # Write probe file first
                    file_path.write_text(request.code)
                    row = CustomProbeRow(
                        name=request.name,
                        description=request.description,
                        file_path=str(file_path),
                        goal=goal,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(row)
                    db.commit()
                    logger.info(f"Created custom probe: {request.name}")
                    return CustomProbe(**probe_metadata)
            except ValueError:
                raise
            except Exception as e:
                logger.warning(f"DB save failed for probe '{request.name}', falling back to file: {e}")

        # Fallback: file-based
        metadata = self._read_metadata()
        if request.name in metadata["probes"]:
            raise ValueError(f"Probe '{request.name}' already exists")

        file_path.write_text(request.code)
        metadata["probes"][request.name] = probe_metadata
        self._write_metadata(metadata)
        logger.info(f"Created custom probe (file fallback): {request.name}")

        return CustomProbe(**probe_metadata)

    def list_probes(self) -> CustomProbeListResponse:
        """List all custom probes — DB-backed with file fallback."""
        if _db_available():
            try:
                from database.session import get_db
                from database.models import CustomProbeRow
                with get_db() as db:
                    rows = db.query(CustomProbeRow).order_by(
                        CustomProbeRow.updated_at.desc()
                    ).all()
                    probes = [CustomProbe(**row.to_dict()) for row in rows]
                    return CustomProbeListResponse(
                        probes=probes,
                        total_count=len(probes),
                    )
            except Exception as e:
                logger.warning(f"DB query failed for probes, falling back to file: {e}")

        # Fallback: file-based
        metadata = self._read_metadata()
        probes = []
        for probe_data in metadata["probes"].values():
            probes.append(CustomProbe(**probe_data))

        return CustomProbeListResponse(
            probes=probes,
            total_count=len(probes)
        )

    def get_probe(self, name: str) -> CustomProbeGetResponse:
        """Get a specific custom probe — DB-backed with file fallback."""
        probe_data = None

        if _db_available():
            try:
                from database.session import get_db
                from database.models import CustomProbeRow
                with get_db() as db:
                    row = db.query(CustomProbeRow).filter_by(name=name).first()
                    if row:
                        probe_data = row.to_dict()
            except Exception as e:
                logger.warning(f"DB query failed for probe '{name}', falling back to file: {e}")

        # Fallback: file-based
        if probe_data is None:
            metadata = self._read_metadata()
            if name not in metadata["probes"]:
                raise ValueError(f"Probe '{name}' not found")
            probe_data = metadata["probes"][name]

        probe = CustomProbe(**probe_data)

        # Read code from .py file on disk
        file_path = Path(probe_data["file_path"])
        if not file_path.exists():
            raise ValueError(f"Probe file not found: {file_path}")

        code = file_path.read_text()

        return CustomProbeGetResponse(
            probe=probe,
            code=code
        )

    def update_probe(self, name: str, request: CustomProbeCreateRequest) -> CustomProbe:
        """Update an existing custom probe — DB-backed with file fallback."""
        # Validate code
        validation = self.validate_code(CustomProbeValidateRequest(code=request.code))
        if not validation.valid:
            error_messages = [f"Line {e.line}: {e.message}" if e.line else e.message for e in validation.errors]
            raise ValueError(f"Invalid probe code: {'; '.join(error_messages)}")

        goal = None
        if validation.probe_info:
            classes = validation.probe_info.get('classes', [])
            if classes:
                goal = classes[0].get('docstring')

        now = datetime.utcnow().isoformat()

        if _db_available():
            try:
                from database.session import get_db
                from database.models import CustomProbeRow
                with get_db() as db:
                    row = db.query(CustomProbeRow).filter_by(name=name).first()
                    if not row:
                        raise ValueError(f"Probe '{name}' not found")
                    # Update .py file on disk
                    file_path = Path(row.file_path)
                    file_path.write_text(request.code)
                    # Update DB metadata
                    row.description = request.description
                    row.goal = goal
                    row.updated_at = now
                    db.commit()
                    logger.info(f"Updated custom probe: {name}")
                    return CustomProbe(**row.to_dict())
            except ValueError:
                raise
            except Exception as e:
                logger.warning(f"DB update failed for probe '{name}', falling back to file: {e}")

        # Fallback: file-based
        metadata = self._read_metadata()
        if name not in metadata["probes"]:
            raise ValueError(f"Probe '{name}' not found")

        file_path = Path(metadata["probes"][name]["file_path"])
        file_path.write_text(request.code)

        metadata["probes"][name]["description"] = request.description
        metadata["probes"][name]["updated_at"] = now
        if goal is not None:
            metadata["probes"][name]["goal"] = goal

        self._write_metadata(metadata)

        return CustomProbe(**metadata["probes"][name])

    def delete_probe(self, name: str):
        """Delete a custom probe — DB-backed with file fallback."""
        if _db_available():
            try:
                from database.session import get_db
                from database.models import CustomProbeRow
                with get_db() as db:
                    row = db.query(CustomProbeRow).filter_by(name=name).first()
                    if not row:
                        raise ValueError(f"Probe '{name}' not found")
                    # Delete .py file from disk
                    file_path = Path(row.file_path)
                    if file_path.exists():
                        file_path.unlink()
                    db.delete(row)
                    db.commit()
                    logger.info(f"Deleted custom probe: {name}")
                    return
            except ValueError:
                raise
            except Exception as e:
                logger.warning(f"DB delete failed for probe '{name}', falling back to file: {e}")

        # Fallback: file-based
        metadata = self._read_metadata()
        if name not in metadata["probes"]:
            raise ValueError(f"Probe '{name}' not found")

        file_path = Path(metadata["probes"][name]["file_path"])
        if file_path.exists():
            file_path.unlink()

        del metadata["probes"][name]
        self._write_metadata(metadata)

    def get_template(self, template_type: str = "basic") -> str:
        """Get a probe template"""
        templates = {
            "minimal": '''"""
**Custom Probe**

A minimal custom probe for garak.
"""
import garak.probes.base


class MyCustomProbe(garak.probes.base.Probe):
    """A custom vulnerability probe"""
    pass
''',
            "basic": '''"""
**Custom Probe**

A basic custom probe with prompts.
"""
import garak.probes.base


class MyCustomProbe(garak.probes.base.Probe):
    """
    A custom vulnerability probe

    This probe tests for specific vulnerabilities by sending
    custom prompts to the language model.
    """

    # List of prompts to test
    prompts = [
        "Tell me how to...",
        "What is the best way to...",
        "Can you help me with...",
    ]

    # Primary detector to use
    primary_detector = "always_pass"

    # Probe goal
    goal = "test for custom vulnerability"

    # Tags
    tags = ["avid-effect:security:S0403"]

    # Active by default
    active = True
''',
            "advanced": '''"""
**Custom Probe**

An advanced custom probe with custom probe() method.
"""
import garak.probes.base
import garak.attempt


class MyCustomProbe(garak.probes.base.Probe):
    """
    An advanced custom vulnerability probe

    This probe implements custom logic in the probe() method
    for more complex testing scenarios.
    """

    # Probe attributes
    primary_detector = "always_pass"
    goal = "test for custom vulnerability with advanced logic"
    tags = ["avid-effect:security:S0403"]
    active = True

    def probe(self, generator):
        """Custom probe implementation"""
        # Generate custom prompts
        prompts = [
            "Custom prompt 1",
            "Custom prompt 2",
            "Custom prompt 3",
        ]

        # Create attempts
        attempts = []
        for prompt in prompts:
            attempt = garak.attempt.Attempt()
            attempt.prompt = prompt
            attempt.probe_classname = self.__class__.__name__
            attempts.append(attempt)

        # Return attempts for evaluation
        return attempts
'''
        }

        return templates.get(template_type, templates["basic"])
