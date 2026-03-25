---
name: "Gdocs"
description: "Intelligent document assistant for Google Docs - analyzes documents, synthesizes meeting notes into executive summaries, and merges content with proper formatting and attribution. For: (1) Merging meeting notes with intelligent synthesis, (2) Document-aware content integration, (3) Professional, presentation-ready output"
tags: "["skill", "gdocs", "document-skills"]"
---

# Google Docs Intelligent Merge Skill

## Overview

This skill transforms raw meeting notes, transcripts, and research into professional, document-appropriate content for Google Docs. It doesn't just insert content - it **analyzes**, **synthesizes**, and **integrates** intelligently.

**Key Innovation:** Converts 3000+ character meeting transcripts into 3-sentence executive summaries that match your document's tone, style, and purpose.

## What This Skill Does

### ❌ What We DON'T Do (Smart Dumping)
```
User: "Merge these meeting notes"
❌ Bad: Appends entire 3000-char transcript to document
Result: Document bloated, unprofessional, not presentation-ready
```

### ✅ What We DO (Intelligent Synthesis)
```
User: "Merge these meeting notes"
✅ Good:
  1. Analyzes document (executive proposal, formal tone)
  2. Extracts key insights from notes
  3. Synthesizes into 3 sentences matching document style
  4. Inserts with proper formatting
  5. Adds attribution comment
Result: Professional, presentation-ready integration
```

## Current Capabilities (Phases 1-5 Complete)

### 1. Document Analysis
- Reads document structure (headings, sections, content)
- Identifies purpose, audience, tone, and style
- Analyzes section length patterns
- Reads existing comments
- Calculates optimal insertion points

### 2. Intelligent Content Synthesis
- **Extracts key insights** from raw source material
- **Matches document tone** (executive vs detailed, formal vs casual)
- **Matches section length** (3 sentences vs 3000 chars)
- **Maintains narrative flow** (natural continuation)
- **Presentation-ready output** (no meeting note artifacts)

### 3. Smart Insertion
- Comment-aware insertion (preserves existing comments)
- Proper formatting (NORMAL_TEXT style, prevents header inheritance)
- Section-targeted placement
- Atomic batch operations

### 4. Source Attribution
- Document-level comments citing source
- Timestamp and author information
- References to full notes location

### 5. Authentication
- OAuth 2.0 secure authentication
- One-time setup with automatic token refresh
- No need to re-authenticate

### 6. Update Tracking
- Automatic update logging to Updates tab/section
- Detection of existing updates locations (tabs and headers)
- Pattern analysis (prepend vs append, formatting)
- Interactive user prompts on first update
- Session-based state tracking

## Setup Required

Before using this skill, you must complete one-time setup (~5-10 minutes):

1. **Set up OAuth credentials**
   - Follow `auth/oauth_setup.md` step-by-step guide
   - Create Google Cloud project
   - Enable Google Docs API and Drive API
   - Download `credentials.json` to `auth/` directory

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Authenticate** (first use only)
   ```bash
   python examples/test_auth.py
   ```
   Browser will open for you to grant permissions. Tokens are saved for future use.

## How to Use This Skill

### Interactive Workflow (Recommended)

When the user provides meeting notes and a Google Doc URL, Claude (in conversation) will:

1. **Read both** documents
2. **Analyze** document purpose, style, and tone
3. **Propose synthesis** with preview:
   ```
   "I'll extract these 3 key insights and add 2-3 sentences to the
   Market Analysis section that match your executive tone:

   [Preview of synthesized content]

   Should I proceed?"
   ```
4. **Execute** after user approval:
   - Synthesize content
   - Insert at optimal location
   - Set NORMAL_TEXT style (proper formatting)
   - Add attribution comment
   - **Log update** to Updates tab (if enabled)

### Updates Tab Tracking (Automatic)

The skill can automatically track changes in an "Updates" tab or section:

**First Update to Document:**
Claude will ask once per document, per session:
```
"Would you like me to create an Updates tab to track changes?
 1. Yes, prepend (newest first)
 2. Yes, append (newest last)
 3. No, don't track"
```

**Existing Updates Detected:**
If the document already has an "Updates", "Changelog", or "Update Log" tab/section:
- Automatically detects the pattern (newest first vs last)
- Logs updates following the established format
- Never prompts the user

**Update Entry Format:**
```
**October 31, 2025**
- Summary: Added market research insights
- Sections modified: Market Analysis
- Source: Customer feedback meeting on 10/31/25
```

See `docs/UPDATES_TAB_USAGE.md` for detailed interaction patterns.

### Python API (Programmatic)

```python
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions

editor = GoogleDocsEditor()
inserter = ContentInserter(editor)

# Merge with intelligent synthesis (handled by Claude in conversation)
result = inserter.merge_content(
    doc_url="https://docs.google.com/document/d/DOC_ID/edit",
    content="[Synthesized content from Claude's analysis]",
    section="Market Analysis",
    options=MergeOptions(
        preserve_comments=True,
        add_source_comment=True,
        source_description="meeting on 2025-10-31"
    )
)

print(f"✓ Inserted at index {result['insertion_point'].index}")
print(f"✓ Comment ID: {result['new_comment_id']}")
```

## Core Principles (MUST FOLLOW)

### 1. ANALYZE FIRST

Before synthesizing any content:
- **Document Purpose:** Proposal? Report? Memo? Presentation?
- **Target Audience:** Executives? Team? Customers? Technical?
- **Style & Tone:** Formal? Casual? Technical? Executive summary?
- **Section Patterns:** Concise (3 sentences) vs detailed (3 pages)?
- **Narrative Flow:** How does this section connect to others?

### 2. EXTRACT INSIGHTS, DON'T DUMP

From source material (meeting notes, transcripts, research):
- What are the **3-5 KEY insights**?
- What **data/evidence** supports the document's thesis?
- What **conclusions** are actionable?
- What can be **safely omitted**?

**Warning Signs:**
- ❌ Copying entire sections of notes
- ❌ Using note-taking language ("Attendees:", "Action Items:")
- ❌ Inserting content 3x longer than existing section
- ❌ Breaking the document's narrative flow

### 3. SYNTHESIZE TO MATCH DOCUMENT

Transform raw content to match:
- **Tone:** Executive summary vs meeting minutes
- **Style:** Polished prose vs bullet points
- **Length:** 2-3 sentences vs detailed paragraphs
- **Flow:** Natural continuation, not interruption

### 4. QUALITY GATES (Before Every Insertion)

- [ ] Does synthesized content match document tone?
- [ ] Is length appropriate for section (not 10x longer)?
- [ ] Does it flow naturally from prior content?
- [ ] Is it presentation-ready (no raw note artifacts)?
- [ ] Would a manager/executive understand it standalone?
- [ ] Is formatting clean (NORMAL_TEXT style applied)?

### 5. THE TEST

**Ask yourself:** "If my boss saw only this document (not the notes), would they understand the insights and be able to make decisions?"

- **If no** → You're dumping notes, not synthesizing insights
- **If yes** → You're doing intelligent integration

## Example: Real Transformation

### Input: Raw Meeting Notes
```
📝 Meeting Notes — Customer Feedback on To-Do App
Date: October 31, 2025
Attendees: Product Manager: Sarah Lin, Customer: Alex Rivera

1. Purpose: To gather customer insights on productivity app features...
2. Customer's Current To-Do App Usage:
   - App: Todoist (primary), used daily for work and personal planning
   - Keeps multiple project lists across devices
   - Integrates with Google Calendar and Slack
   - Uses smart scheduling and recurring tasks
   - Loves Karma system for motivation

3. Pain Points & Improvement Areas:
   - Overwhelming task lists: Wants more intelligent grouping
   - Limited Collaboration: Hard to assign and track shared tasks
   - Lack of Context: Tasks often need attachments
   - Notifications: Too frequent or generic

4. Desired Features: [6 feature requests with details]
5. Product Manager Observations: Customer is power-user adjacent...
6. Next Steps: [3 action items]
7. Summary: Alex's feedback highlights opportunities...

[Total: 3,189 characters]
```

### Target Document Context
```
Market Analysis
The market for productivity applications is competitive, but there is a
clear demand for an app that combines simplicity with powerful features.
We aim to differentiate "AchieveIt" through superior user experience,
robust collaboration tools, and intelligent task management capabilities.

[Tone: Executive summary, 3 sentences, high-level]
```

### Output: Synthesized Integration
```
Market Analysis
The market for productivity applications is competitive, but there is a
clear demand for an app that combines simplicity with powerful features.
We aim to differentiate "AchieveIt" through superior user experience,
robust collaboration tools, and intelligent task management capabilities.

Recent customer research with active Todoist users validates this approach
and reveals specific market opportunities. Users consistently report
"overwhelming task lists" and "lack of context" as primary frustrations,
directly supporting our planned focus mode and contextual attachment
features. Additionally, strong demand emerged for AI-assisted prioritization
and location-aware reminders, capabilities absent in current market leaders.

[Added: 440 characters (3 sentences) vs 3,189 char input]
[Attribution comment: "📊 Enhanced with insights from customer feedback (10/31/25)"]
```

**What Changed:**
- ✅ 86% reduction in length (3,189 → 440 chars)
- ✅ Extracted key insights (pain points, feature gaps)
- ✅ Matched executive tone (formal, high-level)
- ✅ Maintained 3-sentence pattern
- ✅ Natural flow from existing content
- ✅ Presentation-ready quality

## API Reference

### GoogleDocsEditor

Main class for Google Docs operations.

```python
editor = GoogleDocsEditor(
    credentials_path="auth/credentials.json",  # Optional
    token_path="~/.claude-skills/gdocs/tokens.json"  # Optional
)
```

#### Key Methods

**`analyze_document(doc_url_or_id, include_comments=True) -> DocumentAnalysis`**
- Analyzes document structure, sections, and comments
- Returns: DocumentAnalysis with title, sections, total_chars, comments

**`read_document_text(doc_url_or_id) -> str`**
- Reads plain text content of document
- Returns: String of full document text

**`get_document(doc_url_or_id) -> Dict`**
- Retrieves raw Google Docs API response
- Returns: Complete JSON structure

**`extract_doc_id(doc_url_or_id) -> str` (static)**
- Extracts document ID from URL or returns as-is
- Supports: Full URLs, short URLs, or bare IDs

### ContentInserter

Handles intelligent content insertion with comment preservation.

```python
from scripts.content_inserter import ContentInserter, MergeOptions

inserter = ContentInserter(editor)
```

#### Key Methods

**`merge_content(doc_url, content, section=None, options=None) -> Dict`**
- High-level API for merging content
- Handles insertion, formatting, and attribution
- Returns: Dict with success, insertion_point, comment_id

**`calculate_insertion_point(doc_id, section_name=None) -> InsertionPoint`**
- Finds optimal insertion location
- Avoids disrupting existing comments
- Returns: InsertionPoint with index and metadata

**`find_commented_ranges(doc_id) -> List[CommentedRange]`**
- Identifies all text ranges with comments
- Used for comment preservation
- Returns: List of CommentedRange objects

#### MergeOptions

```python
options = MergeOptions(
    preserve_comments=True,        # Avoid disrupting existing comments
    add_source_comment=True,       # Add attribution comment
    source_description="meeting on 2025-10-31",  # Source info
    target_section="Market Analysis"  # Section name
)
```

### CommentManager

Manages comments via Google Drive API.

```python
from scripts.comment_manager import CommentManager

comment_mgr = CommentManager(drive_service)
```

#### Key Methods

**`get_comments(doc_id, include_resolved=False) -> List[Comment]`**
- Retrieves all comments from document
- Returns: List of Comment objects with id, content, author, anchor

**`create_comment(doc_id, content) -> str`**
- Creates document-level comment
- Returns: Comment ID

**`reply_to_comment(doc_id, comment_id, content) -> str`**
- Adds reply to existing comment
- Returns: Reply ID

**`resolve_comment(doc_id, comment_id) -> bool`**
- Marks comment as resolved
- Returns: True if successful

**`delete_comment(doc_id, comment_id) -> bool`**
- Deletes comment
- Returns: True if successful

## Document URL Formats

All of these work:
- Full URL: `https://docs.google.com/document/d/ABC123XYZ/edit`
- Short URL: `docs.google.com/document/d/ABC123XYZ`
- Just ID: `ABC123XYZ`

The skill automatically extracts the document ID.

## Known Limitations

### What Google Docs API Cannot Do
- ❌ Create suggested edits (can only read them)
- ❌ Create text-range comments reliably (anchor field doesn't work)
- ❌ Enable "Suggesting mode" programmatically

### Current Workarounds
- ✅ Use direct edits + document-level attribution comments
- ✅ Version history provides change tracking
- ✅ Comments explain what was synthesized and from where

### What We Handle
- ✅ Comment preservation during edits (insert-then-delete strategy)
- ✅ Formatting inheritance (explicit NORMAL_TEXT style)
- ✅ Section-targeted insertion
- ✅ Intelligent synthesis (not raw dumping)

## Comparison: When to Use This vs .docx Skill

### Use Google Docs skill when:
- ✅ Document lives in Google Drive
- ✅ Need intelligent content synthesis
- ✅ Target audience is executives/managers
- ✅ Want presentation-ready output
- ✅ Real-time collaboration needed
- ✅ Contextual comments explaining changes

### Use .docx skill when:
- ✅ Need formal tracked changes/redlining
- ✅ Legal, academic, or business document review
- ✅ Offline editing required
- ✅ Precise OOXML control needed
- ✅ Traditional Word workflow expected

## Security & Privacy

- **OAuth 2.0** - Industry standard authentication
- **Credentials never in git** - `.gitignore` protects secrets
- **Tokens auto-refresh** - No repeated authentication
- **Minimal scopes** - Only necessary permissions:
  - `https://www.googleapis.com/auth/documents` - Read and write docs
  - `https://www.googleapis.com/auth/drive` - Full Drive access (for comments)

**Revoke access anytime:** https://myaccount.google.com/permissions

## Development Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Authentication & document reading |
| Phase 2 | ✅ Complete | Comment reading & analysis |
| Phase 3 | ✅ Complete | Content insertion with comment preservation |
| Phase 4 | ✅ Complete | Comment creation & management |
| Phase 5 | ✅ Complete | Intelligent content synthesis |
| Phase 6 | 🚧 Planned | Packaging & polish |

**Current Status:** ~95% production-ready. Core functionality working.

## Troubleshooting

### Authentication Issues
```
Problem: "credentials.json not found"
Solution: Follow auth/oauth_setup.md step-by-step
```

```
Problem: "Token expired" or authentication fails
Solution: Delete ~/.claude-skills/gdocs/tokens.json and re-run test_auth.py
```

### Document Access Issues
```
Problem: "Document not found" or "Permission denied"
Solution:
  1. Verify you have at least View access to the document
  2. Check you're logged into correct Google account
  3. Verify document ID is correct
```

### Formatting Issues
```
Problem: Inserted text inherits header formatting
Solution: This is fixed - we explicitly set NORMAL_TEXT style
```

```
Problem: Comments disappear after edit
Solution: Use ContentInserter which preserves comments
```

## Examples

See `examples/` directory:
- `test_auth.py` - Test OAuth setup
- `read_document.py` - Read and display document structure
- `read_comments.py` - View all comments
- `merge_meeting_notes.py` - Simple merge example

See test files:
- `test_comment_preservation.py` - Verified comment preservation
- `real_meeting_notes.txt` - Real customer feedback example
- `intelligent_merge.py` - Experimental intelligent merge

## Files & Architecture

```
gdocs/
├── SKILL.md                      # This file
├── README.md                     # Setup guide
├── requirements.txt              # Python dependencies
│
├── auth/
│   ├── oauth_setup.md           # OAuth configuration guide
│   ├── credentials.json.example # Template for setup
│   └── .gitignore               # Protect secrets
│
├── scripts/
│   ├── auth_manager.py          # OAuth token management (266 lines)
│   ├── gdocs_editor.py          # Main API (254 lines)
│   ├── comment_manager.py       # Comment operations (475 lines)
│   ├── content_inserter.py      # Insertion logic (560 lines)
│   └── intelligent_merger.py    # Experimental analysis (~200 lines)
│
├── examples/                    # Usage examples
├── plans/                       # Implementation documentation
└── tests/                       # Test scripts
```

## Support & Documentation

For detailed information:
1. **Setup:** `auth/oauth_setup.md` - OAuth configuration
2. **Quick start:** `README.md` - Getting started guide
3. **Implementation:** `MASTER_PLAN.md` - Complete phase documentation
4. **Design:** `SKILL_DESIGN.md` - Synthesis principles
5. **Phase 5:** `PHASE_5_PLAN.md` - Intelligent synthesis details

## Future Enhancements

Potential improvements (not committed):
- Template library for different document types
- Multi-section synthesis (split notes across sections)
- Confidence scoring for synthesis quality
- Diff preview before insertion
- Rollback feature
- Style learning (analyze document writing patterns)

---

**Last Updated:** 2025-10-31
**Status:** Production-ready for intelligent meeting notes merging
**Key Innovation:** True content synthesis, not smart dumping
