# Google Docs Skill - Table Manipulation Implementation Plan

## Overview

Implement comprehensive table manipulation capabilities for the gdocs skill (`/Users/mattbernier/projects/claude-skills/document-skills/gdocs/`), enabling programmatic creation, modification, and deletion of tables in Google Docs. This transforms the skill from text-only editing to full document structure manipulation, supporting intelligent synthesis of meeting notes and data into professional tables.

**Current State:** Read-only table support (can search text within tables only)
**Target State:** Full CRUD operations on tables, rows, columns, and cells
**User Value:** Automatic conversion of meeting notes/data into professional tables, programmatic table updates

---

## 🔄 Resuming Work After Restart?

**→ See:** [gdocs-table-manipulation-RESUME.md](./gdocs-table-manipulation-RESUME.md)

This comprehensive resume guide contains:
- ✅ What's been completed (Phases 1-2)
- 📋 What to do next (Phase 3: Row Operations)
- 📁 File locations and test documents
- 🔧 Code structure and API references
- 🚀 Quick start instructions

**Current Status:** Phase 2 Complete (2/10 phases) | Ready for Phase 3

---

## Key Design Decisions

1. **New Module Location**: `scripts/table_manager.py` - Separate from ContentInserter for clean separation of concerns
2. **Index Tracking**: Use helper methods for all index calculations (tables insert extra characters in Google Docs API)
3. **Cell Location Format**: Standardize on `{table_start_index, row_index, column_index}` tuple pattern
4. **Tab Support**: Built-in from day one - all methods accept optional `tab_id` parameter
5. **Batch Operations**: Optimize for bulk updates - single API call for multiple cell updates
6. **Integration Point**: Extend ContentInserter's `merge_content()` with table detection and synthesis
7. **Table Synthesis**: Auto-detect tabular data in meeting notes, create appropriate table structure
8. **Error Strategy**: Graceful degradation - if table operation fails, fall back to text insertion with warning

## Critical Workflow Understanding

### Current Limitation
```python
# SKILL.md claims this works, but it DOESN'T
# "Table: Use InsertTableRowRequest → InsertTextRequest into cells"
# NO TABLE MANIPULATION CODE EXISTS
```

### After Implementation
```python
# Example 1: Create table from meeting notes
result = table_manager.create_table(
    doc_url=url,
    rows=4, columns=3,
    section="Feature Comparison",
    headers=["Feature", "Current", "Proposed"],
    data=[
        ["AI Help", "None", "GPT-4"],
        ["Sync", "Daily", "Real-time"],
        ["Mobile", "Basic", "Full native"]
    ]
)

# Example 2: Update existing table
table_manager.update_cells_bulk(
    doc_url=url,
    table_index=0,
    updates=[
        {'row': 1, 'column': 2, 'content': 'Completed'},
        {'row': 2, 'column': 2, 'content': 'In Progress'}
    ]
)

# Example 3: Intelligent synthesis (ContentInserter integration)
result = inserter.merge_content(
    doc_url=url,
    content=meeting_notes_with_table_data,
    section="Competitive Analysis",
    options=MergeOptions(prefer_table_format=True)
)
# → Automatically creates table if content is tabular
```

## Google Docs API Operations Required

### Available Request Types (API v1)

1. **InsertTableRequest**: Create new table
   ```json
   {"insertTable": {"rows": 3, "columns": 4, "location": {"index": 1}}}
   ```

2. **InsertTableRowRequest**: Add rows
   ```json
   {
     "insertTableRow": {
       "tableCellLocation": {
         "tableStartLocation": {"index": 10},
         "rowIndex": 1,
         "columnIndex": 0
       },
       "insertBelow": true
     }
   }
   ```

3. **DeleteTableRowRequest**: Remove rows
4. **InsertTableColumnRequest**: Add columns
5. **DeleteTableColumnRequest**: Remove columns
6. **InsertTextRequest**: Update cell content (requires cell index)
7. **DeleteContentRangeRequest**: Delete entire table

### API Challenges to Handle

- **Index Tracking**: Tables insert structural characters (API adds hidden elements)
- **Cell Location**: Requires: table start index + row index + column index
- **Tab Support**: Must include `tabId` for multi-tab documents
- **Content Structure**: Cells contain structural elements (paragraphs), not just text

## File Structure

```
claude-skills/document-skills/gdocs/
├── scripts/
│   ├── table_manager.py              # NEW - Core table operations
│   ├── content_inserter.py           # MODIFY - Add table synthesis
│   ├── gdocs_editor.py              # EXISTS - No changes needed
│   └── comment_manager.py           # EXISTS - No changes needed
├── examples/
│   ├── create_comparison_table.py   # NEW - Feature comparison example
│   ├── update_project_timeline.py   # NEW - Timeline update example
│   ├── build_budget_table.py        # NEW - Budget table example
│   └── synthesize_meeting_table.py  # NEW - Meeting notes → table
├── tests/
│   └── test_table_manager.py        # NEW - Comprehensive test suite
├── docs/
│   └── table-operations.md          # NEW - Table usage guide
├── SKILL.md                          # MODIFY - Add table documentation
├── PHASE_6_PLAN.md                  # EXISTS - Detailed technical plan
└── TABLE_CAPABILITIES_SUMMARY.md    # EXISTS - Gap analysis

agents-environment-config/plans/
└── gdocs-table-manipulation.plan.md # THIS FILE
```

## Implementation Tasks

### Phase 1: Core Infrastructure & Table Discovery

**Goal:** Implement TableManager class with table discovery capabilities
**Time Estimate:** 4-5 hours

- [x] **Task 1.1: Create TableManager class skeleton** ✅
  - File: `scripts/table_manager.py`
  - Create class with `__init__(editor)`
  - Import necessary types and dataclasses
  - Set up documentation structure

- [x] **Task 1.2: Implement dataclasses** ✅
  - Create `TableLocation` dataclass (table_index, start_index, end_index, rows, columns)
  - Create `CellLocation` dataclass (table_start_index, row_index, column_index, cell_start_index, cell_end_index)
  - Add proper type hints and documentation

- [x] **Task 1.3: Implement find_tables()** ✅
  - Parse document body for table elements
  - Extract table dimensions (rows, columns)
  - Calculate start/end indices for each table
  - Return list of TableLocation objects
  - Support tab_id parameter for multi-tab documents

- [x] **Task 1.4: Implement get_table_at_index()** ✅
  - Find specific table by zero-based index
  - Return TableLocation or None if not found
  - Support tab_id parameter

- [x] **Task 1.5: Implement find_cell_location()** ✅
  - Calculate exact character indices for a specific cell
  - Handle table structure (rows → cells → content)
  - Return CellLocation with all index information
  - Critical for all cell operations

- [x] **Task 1.6: Create helper method _build_table_cell_location()** ✅
  - Build API-compatible tableCellLocation dict
  - Format: `{tableStartLocation: {index}, rowIndex, columnIndex}`
  - Used by all row/column operations

- [x] **Task 1.7: Test Phase 1** ✅
  - Create test document with known table structure
  - Verify find_tables() discovers all tables correctly
  - Verify get_table_at_index() returns correct table
  - Verify find_cell_location() calculates accurate indices
  - Test with multi-tab documents
  - **Test Result:** ALL TESTS PASSED - https://docs.google.com/document/d/1snQqLXwSYtAjqpW73Lf1WETO99YIYsaBIEEThSeqYxg/edit

### Phase 2: Table Creation

**Goal:** Implement table creation with headers and data
**Time Estimate:** 3-4 hours

- [x] **Task 2.1: Implement create_table() base functionality** ✅
  - File: `scripts/table_manager.py`
  - Accept: doc_url, rows, columns, location_index
  - Build InsertTableRequest
  - Execute via docs_service.batchUpdate()
  - Return TableLocation of created table

- [x] **Task 2.2: Add section-based insertion** ✅
  - Accept optional section parameter
  - Implemented `_find_section_insertion_point()` method
  - Parses document for HEADING_ style paragraphs
  - Returns insertion point after matching heading
  - Falls back to document end if section not found

- [x] **Task 2.3: Add header row support** ✅
  - Accept optional headers list
  - Implemented `_populate_header_row()` method
  - Inserts text into row 0 cells
  - Applies bold formatting to headers
  - Batches all requests for efficiency

- [x] **Task 2.4: Add data population support** ✅
  - Accept optional data parameter (List[List[str]])
  - Populate all data rows after table creation
  - Batch multiple InsertTextRequests for efficiency
  - Validates data dimensions against table dimensions

- [x] **Task 2.5: Add tab support** ✅
  - Accept optional tab_id parameter
  - Include tab_id in all location specifications
  - Full tab support built into all methods

- [x] **Task 2.6: Implement _populate_table_data() helper** ✅
  - Internal method to fill table with data efficiently
  - Calculate cell indices for each data element
  - Build batch requests for all cell updates
  - Single API call for all cell content

- [x] **Task 2.7: Test Phase 2** ✅
  - Test empty table creation ✅
  - Test table with headers only ✅
  - Test table with headers and data ✅
  - Test section-based insertion ✅
  - **Test Result:** ALL TESTS PASSED - https://docs.google.com/document/d/1e34VeVzT4dLw0V9aDKn_2-cfqFCkbKKltrAQBfVRemc/edit

### Phase 3: Row Operations

**Goal:** Implement row insertion and deletion
**Time Estimate:** 2-3 hours

- [ ] **Task 3.1: Implement insert_row() base**
  - Accept: doc_url, table_index, row_position, insert_below
  - Find table and build tableCellLocation
  - Build InsertTableRowRequest
  - Execute and return new row index

- [ ] **Task 3.2: Add cell_data support to insert_row()**
  - Accept optional cell_data list
  - After row insertion, populate cells with data
  - Calculate new cell indices
  - Use InsertTextRequest for each cell

- [ ] **Task 3.3: Implement delete_row()**
  - Accept: doc_url, table_index, row_index
  - Find table and build tableCellLocation
  - Build DeleteTableRowRequest
  - Execute and verify success
  - Update TableLocation dimensions

- [ ] **Task 3.4: Add batch row operations**
  - Implement insert_rows_bulk() for multiple rows
  - Single API call with multiple requests
  - Calculate indices accounting for previous insertions

- [ ] **Task 3.5: Test Phase 3**
  - Test insert row above
  - Test insert row below
  - Test insert row with data
  - Test delete row
  - Verify indices remain accurate after operations
  - Test bulk row insertions

### Phase 4: Column Operations

**Goal:** Implement column insertion and deletion
**Time Estimate:** 2-3 hours

- [ ] **Task 4.1: Implement insert_column() base**
  - Accept: doc_url, table_index, column_position, insert_right
  - Find table and build tableCellLocation
  - Build InsertTableColumnRequest
  - Execute and return new column index

- [ ] **Task 4.2: Add cell_data support to insert_column()**
  - Accept optional cell_data list (data for all rows in new column)
  - After column insertion, populate cells with data
  - Calculate cell indices for each row
  - Batch InsertTextRequests

- [ ] **Task 4.3: Implement delete_column()**
  - Accept: doc_url, table_index, column_index
  - Find table and build tableCellLocation
  - Build DeleteTableColumnRequest
  - Execute and verify success
  - Update TableLocation dimensions

- [ ] **Task 4.4: Add batch column operations**
  - Implement insert_columns_bulk() for multiple columns
  - Handle index shifts from previous insertions
  - Single API call with multiple requests

- [ ] **Task 4.5: Test Phase 4**
  - Test insert column left
  - Test insert column right
  - Test insert column with data
  - Test delete column
  - Verify indices remain accurate
  - Test bulk column insertions

### Phase 5: Cell Operations

**Goal:** Implement cell reading and updating
**Time Estimate:** 3-4 hours

- [ ] **Task 5.1: Implement get_cell_content()**
  - Accept: doc_url, table_index, row, column
  - Use find_cell_location() to get indices
  - Extract text from cell's paragraph elements
  - Return cell content as string
  - Handle empty cells gracefully

- [ ] **Task 5.2: Implement update_cell()**
  - Accept: doc_url, table_index, row, column, content
  - Use find_cell_location() to get cell boundaries
  - Delete existing cell content (DeleteContentRangeRequest)
  - Insert new content (InsertTextRequest)
  - Preserve cell structure (paragraph elements)

- [ ] **Task 5.3: Implement update_cells_bulk()**
  - Accept: doc_url, table_index, updates list
  - Build batch of delete + insert requests for all cells
  - Calculate all indices before building requests (avoid shifting)
  - Single API call with all updates
  - Return success count and failed operations

- [ ] **Task 5.4: Implement _extract_table_data() helper**
  - Extract all cell content from table element
  - Return 2D array (List[List[str]])
  - Used for table reading and display

- [ ] **Task 5.5: Implement _format_as_table_string() helper**
  - Convert table data to human-readable string
  - For debugging and display purposes
  - ASCII table format with borders

- [ ] **Task 5.6: Test Phase 5**
  - Test reading cell content
  - Test updating single cell
  - Test bulk cell updates (5-10 cells)
  - Verify content accuracy after updates
  - Test empty cell handling
  - Test preserving cell formatting

### Phase 6: Table Deletion

**Goal:** Implement table deletion
**Time Estimate:** 1-2 hours

- [ ] **Task 6.1: Implement delete_table()**
  - Accept: doc_url, table_index, tab_id
  - Find table boundaries (start_index, end_index)
  - Build DeleteContentRangeRequest
  - Execute deletion
  - Verify table removed from document

- [ ] **Task 6.2: Add safety checks**
  - Validate table_index exists
  - Optionally require confirmation parameter
  - Clear error messages if table not found

- [ ] **Task 6.3: Test Phase 6**
  - Test deleting table by index
  - Verify table removed from document
  - Test error handling for invalid index
  - Verify surrounding content unaffected

### Phase 7: ContentInserter Integration

**Goal:** Enable table synthesis from meeting notes
**Time Estimate:** 3-4 hours

- [ ] **Task 7.1: Add table_manager to ContentInserter**
  - File: `scripts/content_inserter.py`
  - Import TableManager
  - Initialize in __init__: `self.table_manager = TableManager(editor)`

- [ ] **Task 7.2: Implement _should_create_table()**
  - Analyze content for tabular patterns
  - Check for column headers, data rows
  - Check MergeOptions.prefer_table_format flag
  - Return boolean decision

- [ ] **Task 7.3: Implement _extract_table_structure()**
  - Parse content for table data
  - Extract headers (first row or detect from content)
  - Extract data rows
  - Return: headers list, data list
  - Handle various formats (markdown tables, bullet lists, etc.)

- [ ] **Task 7.4: Enhance merge_content() for tables**
  - After content analysis, check if should create table
  - If yes, call table_manager.create_table()
  - If no, proceed with existing text insertion
  - Add source attribution comment for tables
  - Return table_location in result

- [ ] **Task 7.5: Update MergeOptions**
  - Add prefer_table_format: bool field
  - Add table_has_headers: bool field
  - Add table_style: Optional[str] field (future use)

- [ ] **Task 7.6: Test Phase 7**
  - Test detecting tabular content in meeting notes
  - Test extracting table structure correctly
  - Test automatic table creation
  - Test falling back to text when not tabular
  - Test with prefer_table_format=True
  - Test source attribution on synthesized tables

### Phase 8: Documentation

**Goal:** Update all documentation
**Time Estimate:** 2-3 hours

- [ ] **Task 8.1: Update SKILL.md**
  - File: `SKILL.md`
  - Remove misleading claims about table support
  - Add comprehensive "Working with Tables" section
  - Document all table operations with examples
  - Add table synthesis patterns
  - Add common table patterns by document type
  - Update "Document Structures" section

- [ ] **Task 8.2: Create table-operations.md guide**
  - File: `docs/table-operations.md`
  - Detailed usage guide for TableManager
  - Examples for each operation type
  - Best practices for index handling
  - Troubleshooting common issues

- [ ] **Task 8.3: Update existing phase documentation**
  - Mark PHASE_6_PLAN.md as IN PROGRESS
  - Update PROJECT_SUMMARY.md with Phase 6 status
  - Update MASTER_PLAN.md with table capabilities

- [ ] **Task 8.4: Add inline code documentation**
  - Comprehensive docstrings for all methods
  - Type hints on all parameters
  - Usage examples in docstrings
  - Parameter validation documentation

### Phase 9: Examples

**Goal:** Create comprehensive example scripts
**Time Estimate:** 2-3 hours

- [ ] **Task 9.1: Create create_comparison_table.py**
  - File: `examples/create_comparison_table.py`
  - Feature comparison table example
  - Headers: Feature, Competitor A, Our Product
  - Sample data with 4-5 rows
  - Section-based insertion

- [ ] **Task 9.2: Create update_project_timeline.py**
  - File: `examples/update_project_timeline.py`
  - Update existing timeline table
  - Bulk cell updates for status column
  - Add completion dates

- [ ] **Task 9.3: Create build_budget_table.py**
  - File: `examples/build_budget_table.py`
  - Financial/budget table
  - Headers: Item, Cost, Category, Status
  - Formatted currency values

- [ ] **Task 9.4: Create synthesize_meeting_table.py**
  - File: `examples/synthesize_meeting_table.py`
  - Meeting notes to table conversion
  - Uses ContentInserter with prefer_table_format
  - Shows automatic synthesis workflow

- [ ] **Task 9.5: Add README to examples/**
  - File: `examples/README.md`
  - Overview of all table examples
  - How to run examples
  - Expected outputs

### Phase 10: Testing

**Goal:** Comprehensive test suite
**Time Estimate:** 4-5 hours

- [ ] **Task 10.1: Create test infrastructure**
  - File: `tests/test_table_manager.py`
  - Set up test document with known structure
  - Create fixtures for test data
  - Helper functions for verification

- [ ] **Task 10.2: Table discovery tests**
  - test_find_tables_empty_document()
  - test_find_tables_multiple_tables()
  - test_get_table_at_index()
  - test_find_cell_location()

- [ ] **Task 10.3: Table creation tests**
  - test_create_empty_table()
  - test_create_table_with_headers()
  - test_create_table_with_data()
  - test_create_table_in_section()
  - test_create_table_with_tab_id()

- [ ] **Task 10.4: Row operation tests**
  - test_insert_row_above()
  - test_insert_row_below()
  - test_insert_row_with_data()
  - test_delete_row()
  - test_insert_rows_bulk()

- [ ] **Task 10.5: Column operation tests**
  - test_insert_column_left()
  - test_insert_column_right()
  - test_insert_column_with_data()
  - test_delete_column()
  - test_insert_columns_bulk()

- [ ] **Task 10.6: Cell operation tests**
  - test_get_cell_content()
  - test_update_cell_content()
  - test_update_cells_bulk()
  - test_empty_cell_handling()

- [ ] **Task 10.7: Table deletion tests**
  - test_delete_table()
  - test_delete_nonexistent_table()

- [ ] **Task 10.8: Integration tests**
  - test_synthesize_meeting_notes_to_table()
  - test_table_detection_in_merge_content()
  - test_automatic_table_creation()
  - test_fallback_to_text_when_not_tabular()

- [ ] **Task 10.9: Edge case tests**
  - test_large_table_operations()
  - test_concurrent_table_operations()
  - test_index_tracking_after_multiple_operations()
  - test_tab_id_edge_cases()

- [ ] **Task 10.10: Performance tests**
  - test_bulk_update_50_cells()
  - test_create_large_table_100_rows()
  - test_multiple_table_creation_in_document()

## Timeline & Milestones

### Week 1: Core Implementation
**Days 1-2** (8-10 hours)
- ✅ Phase 1: Core Infrastructure & Table Discovery
- ✅ Phase 2: Table Creation

**Days 3-4** (8-10 hours)
- ✅ Phase 3: Row Operations
- ✅ Phase 4: Column Operations

**Day 5** (4-5 hours)
- ✅ Phase 5: Cell Operations
- ✅ Phase 6: Table Deletion

### Week 2: Integration & Polish
**Days 1-2** (6-8 hours)
- ✅ Phase 7: ContentInserter Integration
- ✅ Phase 8: Documentation (partial)

**Days 3-4** (6-8 hours)
- ✅ Phase 9: Examples
- ✅ Phase 10: Testing (core tests)

**Day 5** (4-5 hours)
- ✅ Phase 8: Documentation (completion)
- ✅ Phase 10: Testing (edge cases & performance)
- ✅ Final review and polish

**Total Time:** 22-28 hours across 2 weeks

### Milestones
- **M1 (End of Week 1):** All table CRUD operations working
- **M2 (Mid Week 2):** ContentInserter integration complete, tables synthesis working
- **M3 (End of Week 2):** Full test coverage, documentation complete, ready for production

## Success Criteria

### Technical Success
- [ ] All table CRUD operations functional (create, read, update, delete)
- [ ] Index tracking accurate across all operations
- [ ] Tab support working for multi-tab documents
- [ ] Batch operations optimized (single API call for multiple updates)
- [ ] Error handling robust with clear error messages
- [ ] 90%+ test coverage for TableManager
- [ ] Zero regressions in existing ContentInserter functionality

### User Value Success
- [ ] Can create tables from meeting notes automatically
- [ ] Can update existing tables programmatically
- [ ] 95%+ time savings vs manual table creation (measured)
- [ ] Professional table formatting matches document style
- [ ] Source attribution on synthesized tables
- [ ] Natural integration with document flow

### Documentation Success
- [ ] SKILL.md accurately reflects all capabilities
- [ ] Clear examples for each operation type
- [ ] Table synthesis patterns documented
- [ ] No misleading claims about functionality
- [ ] Inline documentation comprehensive
- [ ] Usage guide complete with troubleshooting

### Quality Success
- [ ] Tables match document style automatically
- [ ] Cell content properly formatted
- [ ] Proper formatting preserved during operations
- [ ] Graceful error handling with user-friendly messages
- [ ] Performance acceptable for large tables (100+ rows)

## Risk Mitigation

### Risk 1: Index Tracking Complexity
**Likelihood:** High | **Impact:** High

**Mitigation:**
- Create comprehensive helper methods for all index calculations
- Extensive unit tests for index tracking scenarios
- Document index calculation patterns clearly
- Build index validation into all operations
- Reference existing Google Docs API examples

**Contingency:**
- If index tracking proves too complex, simplify operations
- Implement in stages: simple operations first, complex later
- Consider caching document structure between operations

### Risk 2: API Limitations
**Likelihood:** Medium | **Impact:** Medium

**Mitigation:**
- Research API thoroughly before each phase
- Test with real Google Docs during development
- Have fallback strategies for each operation
- Document limitations clearly in SKILL.md
- Verify API behavior with official documentation

**Contingency:**
- If operation not supported, document limitation
- Provide manual workflow alternative
- Request feature from Google (low priority)

### Risk 3: Performance Issues
**Likelihood:** Medium | **Impact:** Low-Medium

**Mitigation:**
- Optimize batch operations from day one
- Use single API calls for multiple updates
- Test with large tables early (100+ rows)
- Implement pagination for very large operations
- Add progress indicators for long operations

**Contingency:**
- If performance poor, implement chunking
- Add async/await for large operations
- Cache document structure when possible

### Risk 4: Tab Support Complexity
**Likelihood:** Low | **Impact:** Medium

**Mitigation:**
- Build on existing tab support from Phase 5
- Test with multi-tab documents throughout development
- Clear error messages for tab-related issues
- Document tab behavior explicitly
- Reuse existing tab handling patterns

**Contingency:**
- If tab support problematic, make tab_id mandatory for multi-tab docs
- Provide clear error when tab_id missing but needed
- Document tab requirements prominently

### Risk 5: Integration Breaking Changes
**Likelihood:** Low | **Impact:** High

**Mitigation:**
- Complete test suite for existing functionality
- Run all existing tests after each phase
- No modifications to gdocs_editor.py or comment_manager.py
- Minimal changes to content_inserter.py (additive only)
- Version control with clear commits per phase

**Contingency:**
- If integration breaks existing features, roll back
- Implement table features as separate flow
- Add feature flag for table synthesis
- Maintain backward compatibility always

## Dependencies

### Code Dependencies
- ✅ gdocs_editor.py - No changes needed
- ✅ comment_manager.py - No changes needed
- ⚠️ content_inserter.py - Modifications required (additive only)
- ✅ Google Docs API v1 - All required operations available
- ✅ Google Drive API v3 - Already integrated

### Knowledge Dependencies
- ✅ Google Docs API table operations (researched)
- ✅ Index tracking patterns (documented in search results)
- ✅ Existing ContentInserter patterns (reviewed)
- ✅ Tab support patterns from Phase 5 (reviewed)

### Testing Dependencies
- ⚠️ Test Google Doc with edit permissions
- ⚠️ OAuth credentials for testing
- ⚠️ Multi-tab test document
- ⚠️ Various table structures for test cases

## Post-Implementation

### Future Enhancements (Phase 7+)

1. **Table Styling (Phase 7)**
   - Border styles and colors
   - Cell background colors
   - Header row styling
   - Alternating row colors
   - Cell padding and alignment

2. **Advanced Cell Operations (Phase 7)**
   - Merge cells horizontally
   - Merge cells vertically
   - Split merged cells
   - Cell formatting (bold, italic, colors)

3. **Smart Table Operations (Phase 8)**
   - Sort table rows by column
   - Filter table data
   - Transpose table (swap rows/columns)
   - Copy table structure to new location

4. **Table Templates (Phase 8)**
   - Pre-defined table templates by use case
   - Template library (comparison, timeline, budget, gantt, etc.)
   - Custom template creation and sharing
   - Template insertion with data

5. **Table Extraction & Export (Phase 9)**
   - Extract table as CSV
   - Extract table as JSON
   - Export to Google Sheets
   - Import from external sources

### Maintenance Considerations

- **Google API Changes**: Monitor Google Docs API changelog for breaking changes
- **Test Suite Maintenance**: Keep tests updated as API evolves
- **Documentation Updates**: Update examples when patterns change
- **Performance Monitoring**: Track operation times, optimize if degrading
- **User Feedback**: Collect usage patterns, add common operations

## Getting Started

### Prerequisites
1. Clone repository: `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/`
2. Verify OAuth credentials configured
3. Have test Google Doc ready with edit permissions
4. Ensure all Phase 1-5 tests passing

### Implementation Order
1. Start with Phase 1 (table discovery) - foundation for all operations
2. Move to Phase 2 (table creation) - provides immediate user value
3. Complete Phases 3-6 (CRUD operations) - full feature set
4. Integrate Phase 7 (synthesis) - intelligent automation
5. Finish Phases 8-10 (docs, examples, tests) - production ready

### First Steps
```bash
cd /Users/mattbernier/projects/claude-skills/document-skills/gdocs/

# Create new file
touch scripts/table_manager.py

# Begin with skeleton
# Copy dataclass definitions from PHASE_6_PLAN.md
# Implement TableManager.__init__()
# Implement find_tables() - first working method

# Test immediately
python -c "from scripts.table_manager import TableManager; print('Import successful')"
```

## Notes & Learnings

### Design Insights
- Tables are structural elements, not just content - require different handling than text
- Index tracking is critical - tables insert many hidden characters
- Batch operations significantly improve performance - always prefer over individual calls
- Tab support should be built-in from start, not retrofitted
- Table synthesis requires understanding document context - leverage existing analysis

### API Quirks Discovered
- Tables insert extra characters for structure (cells, rows, etc.)
- Cell content is in paragraph elements within cells
- tableCellLocation requires both table start and row/column indices
- DeleteContentRange is the way to remove entire table
- No native merge/split cell operations in API

### User Feedback Incorporated
- Original user request: "merge meeting notes into documents"
- User clarification: "formatted, concise, to the point" → led to synthesis feature
- Tables are natural format for comparisons, timelines, budgets
- Auto-detection of tabular data is more valuable than manual table creation

---

**Plan Status:** Ready for Implementation
**Created:** 2025-11-19
**Last Updated:** 2025-11-19
**Next Review:** After Phase 1 completion (table discovery working)
