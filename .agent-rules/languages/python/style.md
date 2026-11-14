# Python Style Guide

## Code Formatting

### PEP 8 Compliance
- Follow PEP 8 style guide
- Use Black formatter with line length of 88 characters

### Flake8 Configuration
When configuring Flake8, you may omit these checks if preferred:
- No trailing whitespace on code lines
- Lines should be shorter than 79 characters (use 88 with Black)
- No blank spaces on empty lines
- One empty line at the end of the file

## Type Hints

### Required Type Hints
- **Use type-hints everywhere** - All functions must have type annotations
- Prefer explicit types over implicit inference
- Use `typing` module for complex types

```python
# ✅ Good - explicit type hints
def calculate_total(items: list[Item]) -> float:
    return sum(item.price for item in items)

# ❌ Bad - no type hints
def calculate_total(items):
    return sum(item.price for item in items)
```

## File System Operations

### Path Handling
- **Prefer `Path` from `pathlib`** over `os.path`
- Use pathlib for all file operations

```python
# ✅ Good - pathlib
from pathlib import Path

data_file = Path("data") / "input.txt"
if data_file.exists():
    content = data_file.read_text()

# ❌ Bad - os.path
import os.path
data_file = os.path.join("data", "input.txt")
```

## Documentation

### Docstring Standards
- Use **Google style docstrings** for all functions, classes, and modules
- Include parameter descriptions and return types
- Document exceptions that may be raised

```python
def process_data(data: list[str], threshold: int = 10) -> dict[str, int]:
    """Process input data and return statistics.
    
    Args:
        data: List of string values to process
        threshold: Minimum count threshold (default: 10)
        
    Returns:
        Dictionary with processed statistics
        
    Raises:
        ValueError: If data is empty or threshold is negative
    """
    # Implementation
```

## Virtual Environments

### Environment Requirements
- **Python always requires venv** - Always use virtual environments
- Never use system Python for project dependencies
- Create virtual environment if it doesn't exist

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

## Code Organization

### Project Structure
- Organize code into logical modules
- Separate concerns: routes, schemas, repositories
- Keep related functionality together

### Import Organization
- Group imports: standard library, third-party, local
- Use absolute imports when possible
- Avoid circular imports

```python
# ✅ Good - organized imports
# Standard library
from pathlib import Path
from typing import Optional

# Third-party
from fastapi import FastAPI
from pydantic import BaseModel

# Local
from .schemas import UserSchema
from .repositories import UserRepository
```

## References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **FastAPI**: See `stacks/python-backend/fastapi.mdc`
