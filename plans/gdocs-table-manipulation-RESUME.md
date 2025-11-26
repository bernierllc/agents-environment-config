# Google Docs Table Manipulation - Resume Guide

**Last Updated:** 2025-11-23
**Status:** Phase 2 Complete ✅ | Ready for Phase 3
**Working Directory:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/`

---

## Quick Resume Instructions

### 1. Navigate to Working Directory
```bash
cd /Users/mattbernier/projects/claude-skills/document-skills/gdocs/
```

### 2. Verify Environment
```bash
# Check Python environment
python3 --version

# Verify OAuth credentials exist
ls -la ~/.claude-skills/gdocs/tokens.json
ls -la ~/.claude-skills/gdocs/credentials.json
```

### 3. Resume Point
**You are ready to start Phase 3: Row Operations**

Continue with implementing:
- `insert_row()` - Add rows to existing tables
- `delete_row()` - Remove rows from tables

---

## What Has Been Completed ✅

### Phase 1: Core Infrastructure & Table Discovery (COMPLETE)
**File:** `scripts/table_manager.py` (lines 1-283)

**Implemented:**
- ✅ `TableLocation` dataclass - Stores table position and dimensions
- ✅ `CellLocation` dataclass - Stores cell indices
- ✅ `find_tables()` - Discovers all tables in document
- ✅ `get_table_at_index()` - Gets specific table by index
- ✅ `find_cell_location()` - Calculates cell indices
- ✅ `_build_table_cell_location()` - Builds API-compatible location dict

**Test Status:** ALL TESTS PASSED ✅
- **Test File:** `test_phase1_table_discovery.py`
- **Test Document:** https://docs.google.com/document/d/1snQqLXwSYtAjqpW73Lf1WETO99YIYsaBIEEThSeqYxg/edit
- **Tests Run:** 6/6 passed

---

### Phase 2: Table Creation (COMPLETE)
**File:** `scripts/table_manager.py` (lines 286-648)

**Implemented:**
- ✅ `create_table()` - Full table creation with options
  - Basic table creation (rows × columns)
  - Optional headers (bold formatted)
  - Optional data population
  - Section-based insertion
  - Tab support for multi-tab docs
- ✅ `_find_section_insertion_point()` - Finds heading sections
- ✅ `_extract_paragraph_text()` - Extracts text from paragraphs
- ✅ `_populate_header_row()` - Populates header cells with bold
- ✅ `_populate_table_data()` - Populates data rows efficiently

**Test Status:** ALL TESTS PASSED ✅
- **Test File:** `test_phase2_table_creation.py`
- **Test Document:** https://docs.google.com/document/d/1e34VeVzT4dLw0V9aDKn_2-cfqFCkbKKltrAQBfVRemc/edit
- **Tests Run:** 8/8 passed
- **Tables Created:** 5 tables (basic, headers-only, full data, 2 section-based)

**Example Usage:**
```python
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.table_manager import TableManager

editor = GoogleDocsEditor()
table_manager = TableManager(editor)

# Create table with headers and data
result = table_manager.create_table(
    doc_url="https://docs.google.com/document/d/YOUR_DOC_ID/edit",
    rows=4,
    columns=3,
    section="Project Timeline",
    headers=["Feature", "Current", "Proposed"],
    data=[
        ["AI Help", "None", "GPT-4"],
        ["Sync", "Daily", "Real-time"],
        ["Mobile", "Basic", "Full native"]
    ]
)
```

---

## What Needs To Be Done Next 📋

### Phase 3: Row Operations (NEXT)
**Estimated Time:** 2-3 hours

#### Task 3.1: Implement insert_row()
**File:** `scripts/table_manager.py`

**Signature:**
```python
def insert_row(
    self,
    doc_id: str,
    table_index: int,
    row_index: int,
    insert_below: bool = True,
    data: Optional[List[str]] = None,
    tab_id: Optional[str] = None
) -> Dict[str, Any]:
    """Insert a row into existing table."""
```

**Requirements:**
- Use `InsertTableRowRequest` from Google Docs API
- Build `tableCellLocation` using `_build_table_cell_location()`
- Support inserting above (`insert_below=False`) or below (`insert_below=True`)
- Optional data to populate new row
- Return success status and new row index

**API Request Format:**
```python
{
    'insertTableRow': {
        'tableCellLocation': {
            'tableStartLocation': {'index': table_start_index},
            'rowIndex': row_index,
            'columnIndex': 0  # Any column works
        },
        'insertBelow': insert_below
    }
}
```

#### Task 3.2: Implement delete_row()
**File:** `scripts/table_manager.py`

**Signature:**
```python
def delete_row(
    self,
    doc_id: str,
    table_index: int,
    row_index: int,
    tab_id: Optional[str] = None
) -> Dict[str, Any]:
    """Delete a row from existing table."""
```

**Requirements:**
- Use `DeleteTableRowRequest` from Google Docs API
- Build `tableCellLocation` for target row
- Validate row_index is within table bounds
- Cannot delete last remaining row (API limitation)
- Return success status

**API Request Format:**
```python
{
    'deleteTableRow': {
        'tableCellLocation': {
            'tableStartLocation': {'index': table_start_index},
            'rowIndex': row_index,
            'columnIndex': 0  # Any column works
        }
    }
}
```

#### Task 3.3: Test Phase 3
**Create:** `test_phase3_row_operations.py`

**Test Cases:**
1. Insert row above (insert_below=False)
2. Insert row below (insert_below=True)
3. Insert row with data
4. Delete row from middle of table
5. Delete row from end of table
6. Verify row count changes
7. Test with tab_id

---

### Remaining Phases

#### Phase 4: Column Operations (2-3 hours)
- `insert_column()` - Add columns
- `delete_column()` - Remove columns

#### Phase 5: Cell Operations (3-4 hours)
- `update_cell()` - Update single cell
- `get_cell_content()` - Read cell content
- `update_cells_bulk()` - Batch cell updates

#### Phase 6: Table Deletion (1 hour)
- `delete_table()` - Remove entire table

#### Phase 7: ContentInserter Integration (2-3 hours)
- Integrate TableManager with ContentInserter
- Add table synthesis from meeting notes
- Auto-detect when content should be table

#### Phase 8: Documentation Updates (1-2 hours)
- Update `SKILL.md` with table examples
- Document all table methods
- Add usage patterns

#### Phase 9: Examples (2-3 hours)
- Create example scripts
- Feature comparison tables
- Project timeline tables
- Budget tables

#### Phase 10: Comprehensive Testing (2-3 hours)
- End-to-end tests
- Multi-tab document tests
- Error handling tests
- Performance tests

---

## Key Files Reference

### Implementation Files
- **Main Implementation:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/scripts/table_manager.py`
- **Editor Class:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/scripts/gdocs_editor.py`
- **Content Inserter:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/scripts/content_inserter.py`

### Test Files
- **Phase 1 Tests:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/test_phase1_table_discovery.py`
- **Phase 2 Tests:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/test_phase2_table_creation.py`
- **Phase 3 Tests:** (To be created) `test_phase3_row_operations.py`

### Planning Documents
- **Main Plan:** `/Users/mattbernier/projects/agents-environment-config/plans/gdocs-table-manipulation.plan.md`
- **Phase 6 Specs:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/PHASE_6_PLAN.md`
- **Gap Analysis:** `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/TABLE_CAPABILITIES_SUMMARY.md`
- **Resume Guide:** `/Users/mattbernier/projects/agents-environment-config/plans/gdocs-table-manipulation-RESUME.md` (this file)

### Test Documents
- **Phase 1:** https://docs.google.com/document/d/1snQqLXwSYtAjqpW73Lf1WETO99YIYsaBIEEThSeqYxg/edit
- **Phase 2:** https://docs.google.com/document/d/1e34VeVzT4dLw0V9aDKn_2-cfqFCkbKKltrAQBfVRemc/edit

### Authentication
- **OAuth Token:** `~/.claude-skills/gdocs/tokens.json`
- **Credentials:** `~/.claude-skills/gdocs/credentials.json`

---

## Code Structure Overview

### TableManager Class Structure
```
TableManager (scripts/table_manager.py)
│
├── Core Dataclasses (lines 37-73)
│   ├── TableLocation
│   └── CellLocation
│
├── Phase 1: Table Discovery (lines 102-283)
│   ├── find_tables()
│   ├── get_table_at_index()
│   ├── find_cell_location()
│   └── _build_table_cell_location()
│
├── Phase 2: Table Creation (lines 286-648)
│   ├── create_table()
│   ├── _find_section_insertion_point()
│   ├── _extract_paragraph_text()
│   ├── _populate_header_row()
│   └── _populate_table_data()
│
├── Phase 3: Row Operations (TO IMPLEMENT)
│   ├── insert_row()
│   └── delete_row()
│
├── Phase 4: Column Operations (TO IMPLEMENT)
│   ├── insert_column()
│   └── delete_column()
│
├── Phase 5: Cell Operations (TO IMPLEMENT)
│   ├── update_cell()
│   ├── get_cell_content()
│   └── update_cells_bulk()
│
└── Phase 6: Table Deletion (TO IMPLEMENT)
    └── delete_table()
```

---

## Testing Strategy

### Running Tests
```bash
# Phase 1 Tests
cd /Users/mattbernier/projects/claude-skills/document-skills/gdocs/
python3 test_phase1_table_discovery.py

# Phase 2 Tests
python3 test_phase2_table_creation.py

# Phase 3 Tests (when created)
python3 test_phase3_row_operations.py
```

### Test Pattern
Each phase follows this pattern:
1. Create test document
2. Set up test data/structure
3. Execute operations
4. Verify results
5. Print summary

All tests use real Google Docs API calls and create actual documents.

---

## Important Technical Notes

### Index Tracking
**CRITICAL:** Tables insert structural characters in Google Docs. After creating/modifying tables:
- Indices shift
- Always re-fetch document to get updated indices
- Use `find_tables()` after table operations to get current positions

### Batch Operations
Always batch multiple API requests:
```python
requests = []
# Build multiple requests
requests.append({'insertText': {...}})
requests.append({'updateTextStyle': {...}})

# Execute in single batch
editor.docs_service.documents().batchUpdate(
    documentId=doc_id,
    body={'requests': requests}
).execute()
```

### Tab Support
All methods accept optional `tab_id`:
- Include in location dicts: `{'index': X, 'tabId': tab_id}`
- Pass through all helper methods
- Test with multi-tab documents

### Error Handling
Current pattern:
```python
try:
    # Operation
    return {'success': True, 'data': result}
except Exception as e:
    return {'success': False, 'message': str(e)}
```

---

## How to Resume Work

### Option 1: Continue with Phase 3
```bash
cd /Users/mattbernier/projects/claude-skills/document-skills/gdocs/

# Tell Claude:
"I'm ready to continue with Phase 3: Row Operations.
Please implement insert_row() and delete_row() methods
in scripts/table_manager.py following the specifications
in gdocs-table-manipulation-RESUME.md"
```

### Option 2: Review Current Implementation
```bash
# Read current implementation
cat scripts/table_manager.py

# Run existing tests to verify
python3 test_phase1_table_discovery.py
python3 test_phase2_table_creation.py

# Tell Claude:
"Please review the current table_manager.py implementation
and verify all Phase 1 and Phase 2 functionality is working
before we proceed to Phase 3"
```

### Option 3: Create Test First (TDD)
```bash
# Tell Claude:
"Please create test_phase3_row_operations.py first
following TDD principles, then implement the methods
to make the tests pass"
```

---

## Progress Tracking

### Phases Complete: 2/10 (20%)
- ✅ Phase 1: Core Infrastructure & Table Discovery
- ✅ Phase 2: Table Creation
- ⏳ Phase 3: Row Operations (NEXT)
- ⏸️ Phase 4: Column Operations
- ⏸️ Phase 5: Cell Operations
- ⏸️ Phase 6: Table Deletion
- ⏸️ Phase 7: ContentInserter Integration
- ⏸️ Phase 8: Documentation Updates
- ⏸️ Phase 9: Examples
- ⏸️ Phase 10: Comprehensive Testing

### Time Invested: ~7 hours
### Time Remaining: ~20 hours
### Overall Progress: ~25%

---

## API Reference Quick Links

### Google Docs API v1 - Tables
- **InsertTableRequest:** https://developers.google.com/docs/api/reference/rest/v1/documents/request#inserttablerequest
- **InsertTableRowRequest:** https://developers.google.com/docs/api/reference/rest/v1/documents/request#inserttablerowrequest
- **DeleteTableRowRequest:** https://developers.google.com/docs/api/reference/rest/v1/documents/request#deletetablerowrequest
- **InsertTableColumnRequest:** https://developers.google.com/docs/api/reference/rest/v1/documents/request#inserttablecolumnrequest
- **DeleteTableColumnRequest:** https://developers.google.com/docs/api/reference/rest/v1/documents/request#deletetablecolumnrequest
- **Table Structure:** https://developers.google.com/docs/api/reference/rest/v1/documents#table

---

## Contact & Support

### If Authentication Fails
1. Check token expiry: `cat ~/.claude-skills/gdocs/tokens.json | grep expiry`
2. Delete token to force re-auth: `rm ~/.claude-skills/gdocs/tokens.json`
3. Run any test script - it will trigger OAuth flow

### If Tests Fail
1. Check working directory: `pwd` should be `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/`
2. Verify Python version: `python3 --version` (should be 3.8+)
3. Check imports: All scripts use `from scripts.gdocs_editor import GoogleDocsEditor`
4. Review error stack trace for specific API errors

### If Stuck
Refer to:
- Main plan: `/Users/mattbernier/projects/agents-environment-config/plans/gdocs-table-manipulation.plan.md`
- Technical specs: `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/PHASE_6_PLAN.md`
- Gap analysis: `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/TABLE_CAPABILITIES_SUMMARY.md`

---

**Ready to resume? Start with Phase 3: Row Operations!** 🚀

Just say: "Continue with Phase 3" and we'll implement `insert_row()` and `delete_row()`.
