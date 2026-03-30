---
name: "gdocs"
description: "Writes and updates Google Docs with intelligent content synthesis. Transforms raw content (notes, transcripts, research, drafts) into professional, document-appropriate text with proper formatting and attribution. Supports multi-tab documents, structure-aware insertion (tables, lists, paragraphs), and automatic style matching."
tags: ["skill"]
---


# Google Docs Writing and Editing Skill

## When to Use This Skill

Use this skill when the user:
- Wants to write new content to a Google Doc
- Provides content to add or merge into an existing Google Doc
- Has a Google Doc URL and content that needs intelligent synthesis (not raw dumping)
- Needs professional, presentation-ready output
- Wants content that matches the document's existing tone and style
- Needs to update specific tabs or sections in a multi-tab document

## File Format Detection (CRITICAL FIRST STEP)

**CRITICAL:** URL patterns alone CANNOT distinguish Word documents from Google Docs!

Both Word documents and native Google Docs can have the **same URL format**:
```
https://docs.google.com/document/d/.../edit
```

### The Problem

- ❌ **Cannot detect by URL** - Both formats use `docs.google.com/document/d/...`
- ❌ **Cannot detect by appearance** - Google Drive shows both in the same UI
- ✅ **MUST detect by MIME type** - Requires Drive API call

### Supported vs Unsupported Formats

- ✅ **Google Docs format** - `application/vnd.google-apps.document`
  - Can be edited via Google Docs API
  - Native cloud format

- ❌ **Word documents (.docx)** - `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - **Cannot be edited via Google Docs API**
  - Requires conversion or docx skill
  - Displays in Google Docs UI but remains .docx format

### Detection Requirement

**You MUST handle potential Word documents gracefully.**

**When attempting to edit, expect potential HttpError 404:**
```python
try:
    document = editor.get_document(doc_id)
except HttpError as e:
    if e.resp.status == 404:
        # This might be a Word document
        # Inform user about the limitation
```

### User Communication Pattern

**If you encounter HttpError 404 when accessing a document:**

```
❌ Don't just say: "Document not found"

✅ Instead say:
"I'm unable to access this document via the Google Docs API. This could mean:

1. The document might be a Word file (.docx) rather than a native Google Doc
   - Word documents cannot be edited programmatically via the Google Docs API
   - They need to be converted to Google Docs format first

2. The document may not exist or I may lack permission

Could you check if this is a Word document? If so, you can:
- Convert it: File → Save as Google Docs
- Use the docx skill instead (if available)
- Share the converted Google Docs URL with me"
```

### Why This Matters

**Example from real user:**
```
Word document:  https://docs.google.com/document/d/1kkcUPyLdmwcGIeN8byK_iQ-hu1Dx6NWk/edit
Google Doc:     https://docs.google.com/document/d/1xZDW-RvrYEYJ31Ubg3OEv4IsUx2JlCXvGUTE2vLvwWg/edit

Both have IDENTICAL URL patterns!
Only MIME type reveals the difference.
```

## Core Workflow

**PREREQUISITE: File format verified as Google Docs format (see File Format Detection section)**

**6-Step Process:**
1. **Analyze Document** - Structure, purpose, audience, tone, formatting
2. **Analyze Source Material** - Extract 3-5 KEY insights, not all details
3. **Synthesize Content** - Match tone, style, length; identify contextual placement
4. **Show Preview & Get Approval** - Show what AND where; wait for approval
5. **Execute Merge** - Insert with color coding, attribution, proper formatting
6. **Review and Verify** (MANDATORY) - Complete full Review Checklist

**For detailed workflow checklist, see Workflow Checklist section below.**

## Critical Principles

### ANALYZE FIRST - ALWAYS
Before synthesizing ANY content:
- What is the document's purpose? (Proposal? Report? Memo?)
- Who is the audience? (Executives? Team? Customers?)
- What is the style? (Formal? Casual? Technical?)
- What are the section patterns? (Concise vs detailed?)

### EXTRACT INSIGHTS, DON'T DUMP
From source material:
- What are the **3-5 KEY insights**? (Not everything!)
- What data/evidence supports the thesis?
- What conclusions are actionable?
- What can be safely omitted?

**Warning Signs You're Dumping:**
- ❌ Copying entire sections of notes
- ❌ Using note-taking language ("Attendees:", "Action Items:")
- ❌ Inserting content 3x+ longer than existing sections
- ❌ Breaking the document's narrative flow

### SYNTHESIZE TO MATCH
Transform raw content to match:
- **Tone:** Executive summary vs meeting minutes
- **Style:** Polished prose vs bullet points
- **Length:** 2-3 sentences vs detailed paragraphs
- **Flow:** Natural continuation, not interruption

**Quality verification:** See Professional Quality Check in Review Checklist below (mandatory after every insertion).

### THE TEST
**Ask yourself:** "If my boss saw only this document (not the notes), would they understand the insights and be able to make decisions?"

- **If no** → You're dumping notes, not synthesizing insights
- **If yes** → You're doing intelligent integration

## Color Coding System

**CRITICAL:** All document updates must use this EXACT color coding system to show what changed.

### ⚠️ MANDATORY COLOR SYSTEM - READ THIS FIRST ⚠️

**ABSOLUTE REQUIREMENTS:**
1. **ONLY 5 colors allowed:** Blue, Red, Green, Orange, Purple (see table below)
2. **EXACT RGB values:** No variations, no shades, no "light" or "dark" versions
3. **NO custom colors:** Do not create your own color coding system
4. **NO color adaptations:** Colors are for tracking changes, not aesthetics

**If you are thinking:**
- "I'll use a different shade of blue" → STOP. Use RGB(0.0, 0.0, 1.0) exactly.
- "I'll create a more nuanced system" → STOP. Use only the 5 colors below.
- "Light orange for AI-synthesized content" → STOP. Orange = moved content only.
- "Any blue is fine" → STOP. Blue = RGB(0.0, 0.0, 1.0) EXACTLY.

### ONLY THESE COLORS - NO EXCEPTIONS

**You MUST use these exact RGB values. Do NOT invent your own colors.**

| Color | Exact RGB | Use For | When NOT to Use |
|-------|-----------|---------|-----------------|
| 🔵 **Blue** | `0.0, 0.0, 1.0` | ALL new content | Never use other shades of blue |
| 🔴 **Red + Strikethrough** | `1.0, 0.0, 0.0` | Existing text that conflicts | Do not use for warnings or emphasis |
| 🟢 **Green** | `0.0, 0.5, 0.0` | Replacement text (after red) | Never standalone without red conflict |
| 🟠 **Orange** | `1.0, 0.65, 0.0` | ONLY moved content | Not for "synthesis" or "mixed" content |
| 🟣 **Purple Italic** | `0.5, 0.0, 0.5` | Source attribution ONLY | Not for any other notes or comments |

### Rationalization Table - Color Coding

| Rationalization | Reality |
|-----------------|---------|
| "I'll use a lighter blue for AI-synthesized content" | NO. Blue = RGB(0, 0, 1.0) exactly. No variations. |
| "I'll create a more nuanced color system" | NO. Use ONLY the 5 colors above. No custom systems. |
| "Light orange represents mixed AI/human content" | NO. Orange = moved content only. Use blue for new content regardless of source. |
| "I'll use yellow for highlighting important parts" | NO. Yellow is not in the system. Use blue for new content. |
| "Different shades mean different things" | NO. EXACT RGB values only. No shades or variations. |
| "I can adapt the colors to fit the document theme" | NO. Colors are for change tracking, not aesthetics. Use exact values. |
| "The skill says 'blue' so any blue works" | NO. Blue = RGB(0, 0, 1.0) EXACTLY. No other blues. |

### Color Meanings

#### 🔵 Blue Text - New Content
**Use for:** All newly inserted content

**How to apply:**
```python
{
    'updateTextStyle': {
        'range': {'startIndex': X, 'endIndex': Y},
        'textStyle': {
            'foregroundColor': {
                'color': {
                    'rgbColor': {'red': 0.0, 'green': 0.0, 'blue': 1.0}
                }
            }
        },
        'fields': 'foregroundColor'
    }
}
```

#### 🔴 Red Strikethrough - Conflicting Existing Text
**Use for:** Existing text that contradicts new information

**How to apply:**
```python
{
    'updateTextStyle': {
        'range': {'startIndex': X, 'endIndex': Y},
        'textStyle': {
            'foregroundColor': {
                'color': {
                    'rgbColor': {'red': 1.0, 'green': 0.0, 'blue': 0.0}
                }
            },
            'strikethrough': True
        },
        'fields': 'foregroundColor,strikethrough'
    }
}
```

#### 🟢 Green Text - Replacement Content
**Use for:** New text that replaces conflicting text (place immediately after red strikethrough)

**How to apply:**
```python
{
    'updateTextStyle': {
        'range': {'startIndex': X, 'endIndex': Y},
        'textStyle': {
            'foregroundColor': {
                'color': {
                    'rgbColor': {'red': 0.0, 'green': 0.5, 'blue': 0.0}
                }
            }
        },
        'fields': 'foregroundColor'
    }
}
```

#### 🟠 Orange Text - Moved Content
**Use for:** Content that was moved from one location to another

**How to apply:**
```python
{
    'updateTextStyle': {
        'range': {'startIndex': X, 'endIndex': Y},
        'textStyle': {
            'foregroundColor': {
                'color': {
                    'rgbColor': {'red': 1.0, 'green': 0.65, 'blue': 0.0}
                }
            }
        },
        'fields': 'foregroundColor'
    }
}
```

#### 🟣 Purple Italic - Source Attribution
**Use for:** Inline notes about what changed and where it came from

**Format:** `(from: [source], [date] - [what changed])`

**How to apply:**
```python
{
    'updateTextStyle': {
        'range': {'startIndex': X, 'endIndex': Y},
        'textStyle': {
            'foregroundColor': {
                'color': {
                    'rgbColor': {'red': 0.5, 'green': 0.0, 'blue': 0.5}
                }
            },
            'italic': True
        },
        'fields': 'foregroundColor,italic'
    }
}
```

### Color Coding Patterns

#### Pattern 1: Simple Addition
```
Existing text remains black. New research shows strong adoption rates.
                                ↑ blue text starts here              ↑ ends here
(from: Q4 customer survey - added supporting data)
↑ purple italic attribution
```

#### Pattern 2: Contradiction with Replacement
```
Existing text. Old claim: 45% adoption red strikethrough.
                          ↑ red strikethrough starts
                                                         ↑ ends
Updated: 73% adoption green text
         ↑ green replacement text
(from: Q4 2024 survey - updated adoption rate)
↑ purple italic attribution
```

#### Pattern 3: Content Movement
```
[At new location]
This paragraph was moved from section 2. orange text
                                          ↑ orange for moved content
(moved from: Section 2, paragraph 3)
↑ purple italic attribution explaining move
```

#### Pattern 4: Edited Text
```
Original sentence with minor edits in the middle of text.
                        ↑ edited portion could be blue or another color
(edited for clarity - original: "with some edits")
↑ purple italic showing what changed
```

### Color Coding Checklist

**Before finalizing ANY document update:**
- [ ] All new content marked in BLUE
- [ ] Conflicting old content marked RED with STRIKETHROUGH
- [ ] Replacement content marked GREEN (immediately after red)
- [ ] Moved content marked ORANGE
- [ ] ALL changes have PURPLE ITALIC source notes
- [ ] Source notes include: source name, date, what changed
- [ ] Color coding is CONSISTENT throughout document

### Common Mistakes

❌ **Don't:** Leave new content as default black text
✅ **Do:** Mark ALL new content in blue (RGB 0.0, 0.0, 1.0)

❌ **Don't:** Delete conflicting text without showing it
✅ **Do:** Mark conflicting text red with strikethrough, add green replacement

❌ **Don't:** Use inconsistent attribution format
✅ **Do:** Always use purple italic `(from: source - what changed)`

❌ **Don't:** Skip color coding when "in a hurry"
✅ **Do:** Color coding is MANDATORY, no exceptions

❌ **Don't:** Invent your own color coding system
✅ **Do:** Use ONLY the 5 colors above with EXACT RGB values

❌ **Don't:** Use "light blue" or "light orange" or any shade variations
✅ **Do:** Use the EXACT RGB values specified - no variations

❌ **Don't:** Think "blue" means any shade of blue
✅ **Do:** Blue means RGB(0.0, 0.0, 1.0) EXACTLY

## Professional Editor Mindset

**You are not just inserting text - you are a professional document writer and editor who takes pride in their work.**

### Core Principles

#### Quality Over Speed
- Never "dump" content and move on
- Take time to get formatting right
- Review your work like a professional

#### Contextual Awareness
- Understand where content fits in section flow
- Don't just insert at the top or bottom
- Consider narrative arc: setup → evidence → conclusion

#### Document Improvement
- Always look for ways to improve the overall document
- Notice redundancies, inconsistencies, flow issues
- Suggest improvements even if not explicitly asked

### What Professional Editors Do

**1. Understand Context**
- Read the full section, not just the insertion point
- Understand how new content relates to existing content
- Consider the document's purpose and audience

**2. Place Content Thoughtfully**
- After lists when adding supporting evidence
- Before conclusions when adding data
- Between setup and conclusion when adding analysis
- NEVER just at the top of a section without considering flow

**3. Match Document Style**
- Use the same fonts, sizes, spacing
- Match heading styles
- Match bullet/numbering styles
- Maintain consistent voice and tone

**4. Review and Refine**
- Re-read what you inserted
- Check that it flows naturally
- Verify formatting is consistent
- Look for improvement opportunities

**5. Suggest Improvements**
- "I notice sections 2 and 3 both discuss pricing - consider consolidating"
- "The transition from Marketing to Sales could be smoother"
- "Consider adding subheadings to break up this long section"
- "This terminology is inconsistent with section 1"

**Quality verification:** Complete the mandatory Review Checklist after EVERY insertion (see below).

### Red Flags - You're NOT Being Professional

❌ Inserting at top of section without considering flow
❌ Using default formatting instead of matching document
❌ Not reviewing what you added
❌ "Good enough" mindset
❌ Ignoring document quality issues
❌ Rushing because of time pressure

✅ Taking pride in document quality
✅ Thoughtful contextual placement
✅ Careful formatting match
✅ Thorough review
✅ Suggesting improvements
✅ Professional standards under ALL circumstances

## Review Checklist (MANDATORY After EVERY Insertion)

**After inserting content, you MUST complete this checklist. No exceptions.**

### Step 1: Re-read Inserted Content

**Action:** Call `get_document()` again to fetch updated content

**Verify:**
- [ ] Content appears in correct location
- [ ] No text was accidentally modified
- [ ] No formatting issues introduced

### Step 2: Verify Color Coding

**Check ALL of the following:**
- [ ] **Blue text:** All new content marked blue? No black text in new content?
- [ ] **Red strikethrough:** Conflicting text marked correctly?
- [ ] **Green replacement:** Replacement text marked and placed immediately after red?
- [ ] **Orange text:** Moved content marked?
- [ ] **Purple italic attribution:** ALL changes have source notes?
- [ ] **Attribution format:** Consistent `(from: source, date - what changed)` format?

**If ANY color coding is wrong:** Fix it immediately before proceeding.

### Step 3: Verify Formatting Match

**Compare new content to existing document:**
- [ ] **Font:** Matches document font family?
- [ ] **Size:** Matches surrounding text size?
- [ ] **Spacing:** Line spacing matches?
- [ ] **Bullets/Numbering:** Style matches existing lists?
- [ ] **Headings:** If added headings, style matches existing?
- [ ] **Emphasis:** Bold/italic usage consistent with document?

**If ANY formatting doesn't match:** Fix it immediately.

### Step 4: Assess Contextual Fit

**Read the full section (not just inserted content):**
- [ ] **Flow:** Does new content flow naturally from previous paragraph?
- [ ] **Placement:** Is content in the right spot within section (not lazily dropped at top)?
- [ ] **Transition:** Does transition to next paragraph make sense?
- [ ] **Voice:** Does tone/voice match surrounding content?
- [ ] **Purpose:** Does insertion serve the section's purpose?

**If flow is awkward:** Consider moving content or rewriting transitions.

### Step 5: Professional Quality Check

**Ask yourself:**
- [ ] **Readability:** Would a reader understand this without the source material?
- [ ] **Professionalism:** Is this presentation-ready for the intended audience?
- [ ] **Completeness:** Are there any gaps in logic or information?
- [ ] **Clarity:** Is the writing clear and concise?
- [ ] **Pride:** Would you be proud to show this to a colleague?

**If quality is not professional:** Refine before finalizing.

### Step 6: Document Improvement Suggestions

**Scan the full document for opportunities:**
- [ ] **Redundancy:** Are multiple sections saying the same thing?
- [ ] **Inconsistency:** Are terms/formats used inconsistently?
- [ ] **Flow:** Are there awkward transitions between sections?
- [ ] **Structure:** Could reorganization improve readability?
- [ ] **Completeness:** Are there gaps that should be addressed?
- [ ] **Clarity:** Are any sections unclear or confusing?

**Always provide suggestions when improvements are possible.**

### Reporting Results

**After completing checklist, report to user:**

```
✅ Review Complete:
- Color coding: All new content marked blue, source attribution in purple italic
- Formatting: Matches document (Arial 11pt, 1.15 spacing)
- Contextual fit: Inserted after bullet list as supporting evidence, flows naturally
- Quality: Professional, presentation-ready

💡 Suggestions for improvement:
- Consider consolidating Sections 2 and 3 (both discuss pricing strategy)
- Add subheadings to Section 4 (currently one long block of text)
- Terminology: "users" vs "customers" used inconsistently - recommend standardizing
```

### Review Failures - What to Do

**If review reveals issues:**
1. **Fix them immediately** - Don't leave problems in the document
2. **Report what you fixed:** "Fixed formatting mismatch - updated to Arial 11pt"
3. **Re-review after fixes:** Complete checklist again

**Never:**
❌ Skip review because "I'm confident it's right"
❌ Ignore issues found during review
❌ Report "looks good" without actually checking
❌ Rush review due to time pressure

## Example: The Transformation

### Input: Raw Meeting Notes (3,189 chars)
```
📝 Meeting Notes — Customer Feedback on To-Do App
Date: October 31, 2025
Attendees: Product Manager: Sarah Lin, Customer: Alex Rivera

1. Purpose: To gather customer insights on productivity app features...
2. Customer's Current To-Do App Usage:
   - App: Todoist (primary), used daily
   - Keeps multiple project lists
   - Integrates with Google Calendar and Slack
   [... detailed notes continuing for 3,000+ characters ...]
```

### Target Document Context
```
Market Analysis
The market for productivity applications is competitive, but there is a
clear demand for an app that combines simplicity with powerful features.

[Tone: Executive summary, 3 sentences, high-level]
```

### Output: Synthesized Integration (440 chars)
```
Recent customer research with active Todoist users validates this approach
and reveals specific market opportunities. Users consistently report
"overwhelming task lists" and "lack of context" as primary frustrations,
directly supporting our planned focus mode and contextual attachment
features. Additionally, strong demand emerged for AI-assisted prioritization
and location-aware reminders, capabilities absent in current market leaders.
(from: customer feedback with Alex Rivera, 10/31/25)
```

**Transformation:**
- 86% reduction in length (3,189 → 440 chars)
- Extracted key insights only
- Matched executive tone perfectly
- Natural flow from existing content
- Presentation-ready quality
- Visual attribution marker

## Working with Document Structures

Google Docs contain various structural elements (paragraphs, tables, lists, headers/footers, section breaks).

**Before inserting, detect target structure and use the appropriate API request:**

### Insertion Methods by Structure

- **Table:** Use `InsertTableRowRequest` → `InsertTextRequest` into cells
- **List:** Use `InsertTextRequest` → `CreateParagraphBulletsRequest`
- **Paragraph:** Use `InsertTextRequest` with NORMAL_TEXT style

### Synthesis by Target Structure

Match your content to the target structure:
- **Executive Summary** → Paragraphs (2-3 polished sentences)
- **Feature List** → Bullet points (one per feature)
- **Timeline** → Table rows (Milestone | Date | Owner)
- **Technical Specs** → Numbered list (proper ordering)

### Common Patterns by Document Type

- **Executive Proposal:** Paragraphs + occasional tables for data
- **Technical Specification:** Numbered lists + tables for parameters
- **Project Plan:** Timeline tables + task lists + status paragraphs
- **Meeting Notes:** Numbered agenda + discussion paragraphs + action items list

**For complete structure handling details, see `document-structures-reference.md`:**
- Detection strategy and code examples
- Insertion decision tree
- Structure-aware synthesis patterns
- Error prevention checklist

## Working with Document Tabs

Google Docs supports **multiple tabs within a single document** (similar to spreadsheet tabs).

**CRITICAL:** Always use `includeTabsContent=True` when calling `get_document()`.

### Key Requirements

1. **Extract tab ID from URL** - Look for `?tab=t.xxxxx` parameter
2. **Request all tabs** - Use `includeTabsContent=True` in API call
3. **Target correct tab** - Use tab ID from URL or default to first tab
4. **Include tab ID in requests** - Add tabId to all insertion/update locations

### Quick Example
```python
# Get document with tabs
doc = docs_service.documents().get(
    documentId=doc_id,
    includeTabsContent=True
).execute()

# Extract tab ID from URL and find target tab
tab_id = extract_tab_from_url(url)
target_tab = find_tab_by_id(doc['tabs'], tab_id) if tab_id else doc['tabs'][0]

# Insert with tab ID
requests = [{
    'insertText': {
        'location': {'index': idx, 'tabId': target_tab['tabProperties']['tabId']},
        'text': content
    }
}]
```

**For complete tab handling details, see `tabs-reference.md`:**
- Tab API patterns and document structure
- Tab detection and extraction code
- Nested (child) tabs handling
- Common mistakes and troubleshooting

## Technical Implementation

### Location
The skill files are in: `/Users/mattbernier/projects/claude-skills/document-skills/gdocs/`

### Setup Required (One-Time)
User must complete OAuth setup first:
1. Follow `auth/oauth_setup.md` in skill directory
2. Run `python examples/test_auth.py` to authenticate
3. Tokens saved to `~/.claude-skills/gdocs/tokens.json`

### Usage in Conversation
```python
from scripts.gdocs_editor import GoogleDocsEditor
from scripts.content_inserter import ContentInserter, MergeOptions

editor = GoogleDocsEditor()
inserter = ContentInserter(editor)

# After synthesizing content (YOU do this in conversation)
result = inserter.merge_content(
    doc_url="https://docs.google.com/document/d/DOC_ID/edit",
    content="[Your synthesized content]",
    section="Market Analysis",
    options=MergeOptions(
        preserve_comments=True,
        add_source_comment=True,
        add_inline_attribution=True,  # Italic purple "(from: ...)" text
        source_description="customer feedback, 10/31/25"
    )
)
```

## Attribution System (Three Layers)

### 1. Contextual Comment (In Comments Panel)
```
📝 Added from customer feedback (10/31/25)

📍 Location: Paragraph #12
📝 Context: "...Recent customer research validates..."
```

### 2. Inline Attribution (In Document Text)
```
...absent in current market leaders. (from: customer feedback, 10/31/25)
                                       ↑ italic purple text
```

### 3. Proper Formatting
- NORMAL_TEXT style (prevents header inheritance)
- Preserves existing comments
- Professional appearance

## Error Handling

If insertion fails:
- Check document exists and user has edit permissions
- Verify section name matches (case-insensitive search)
- Falls back to document end if section not found
- Graceful fallback if comment creation fails

## Known Limitations

### Google API Constraints
- ❌ Cannot create "pinned" text-highlighting comments
- ❌ Comments appear in panel, not inline (Google's limitation)
- ❌ **Cannot edit Word documents (.docx)** - Only works with native Google Docs format
- ✅ **Our workaround:** Inline purple text + contextual comment with paragraph #

### File Format Requirements
- ✅ **Supported:** Google Docs format (`application/vnd.google-apps.document`)
- ❌ **Not Supported:** Word documents (`.docx`), PDF, plain text, or other formats
- ⚠️ **Critical:** URL pattern does NOT indicate file type
  - Both Word docs and Google Docs use: `docs.google.com/document/d/.../edit`
  - Must detect format via MIME type or catch 404 errors gracefully

### What We Handle
- ✅ Comment preservation during edits
- ✅ Formatting inheritance (explicit NORMAL_TEXT)
- ✅ Section-targeted insertion
- ✅ Intelligent synthesis (not raw dumping)
- ✅ Visual attribution markers
- ✅ File format detection and user communication

## Workflow Checklist

When user provides meeting notes + Google Doc:

1. [ ] **Extract tab ID from URL** - Check for `?tab=` parameter
2. [ ] **Read document with tabs support** - Use `includeTabsContent=True`
3. [ ] **If HttpError 404** - May be Word document (inform user with conversion options)
4. [ ] **Target correct tab** - Use tab ID from URL or default to first tab
5. [ ] **Analyze document** (purpose, audience, tone, style, formatting) from target tab's content
6. [ ] **Read source material** and extract key insights
7. [ ] **Synthesize content** matching document style and determine contextual placement
8. [ ] **Show preview to user:** "I'll add X sentences to [Section] AFTER the list..."
9. [ ] **Get user approval**
10. [ ] **Execute merge** with color coding and attribution, including tab ID in insertion
11. [ ] **MANDATORY REVIEW** - Complete full Review Checklist:
    - Re-read inserted content
    - Verify color coding (blue, red/green, orange, purple italic)
    - Check formatting matches (fonts, sizes, spacing)
    - Assess contextual fit (flow, placement, transitions)
    - Professional quality check
    - Suggest document improvements
12. [ ] **Report review results** to user with improvement suggestions
13. [ ] **Fix any issues** found during review
14. [ ] **Confirm success** and provide document URL

## Success Metrics

- ✅ 99.7% time savings (5 seconds vs 15-20 minutes manual)
- ✅ 86% length reduction (while preserving key insights)
- ✅ Presentation-ready output (no cleanup needed)
- ✅ Visual attribution (easy to see what was inserted)
- ✅ Professional quality (executive-appropriate)

---

**Remember:** This skill is about **intelligent synthesis**, not smart location finding. The value is in transformation, not insertion mechanics.
