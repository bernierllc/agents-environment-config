---
name: "Gslides"
description: "Comprehensive capabilities for creating, editing, and enhancing Google Slides presentations programmatically. Includes foundation operations, creation basics, visual design, data visualization, intelligent AI-powered content, and quality/polish features."
tags: "["skill", "gslides", "document-skills"]"
---

# Google Slides Skill

## Overview

The Google Slides skill provides comprehensive capabilities for creating, editing, and enhancing Google Slides presentations programmatically. This skill enables AI agents and automation workflows to generate professional presentations with advanced features including:

- **Foundation**: Create, read, and analyze presentations
- **Creation Basics**: Slides, text, shapes, and layouts
- **Visual Design**: Brand guidelines, themes, visual composition, WCAG accessibility
- **Data Visualization**: Charts, tables, images following Analytics Reporter principles
- **Intelligent Content**: AI-powered content generation, story arc, personality injection
- **Quality & Polish**: Quality checks, collaboration features, attribution, production validation

Built on the Google Slides API v1 and Anthropic Claude AI, this skill transforms presentation creation from manual design work into intelligent, automated workflows while maintaining professional quality standards.

## Quick Start

Create your first presentation in 3 lines of code:

```python
from scripts.gslides_editor import GoogleSlidesEditor

# Initialize (OAuth will open browser for first-time auth)
editor = GoogleSlidesEditor()

# Create presentation
result = editor.create_presentation('My First Presentation')
print(f"Created: {result['pres_url']}")
```

## Installation

### Prerequisites

- Python 3.8 or higher
- Google Cloud Project with Slides API enabled
- ~~Anthropic API key~~ **No longer needed!** AI features work through Claude skill invocation

### Step 1: Install Dependencies

```bash
cd /path/to/gslides/
pip install -r requirements.txt
```

### Step 2: Enable Google Slides API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Google Slides API" and "Google Drive API"
4. Create OAuth 2.0 credentials (Desktop application)
5. Download credentials as `credentials.json`

### Step 3: Configure OAuth

```bash
# Place credentials in auth directory
cp ~/Downloads/credentials.json auth/credentials.json

# Test authentication
python examples/test_auth.py
```

The browser will open for first-time OAuth consent. After authorization, tokens are saved to `auth/token.json` for future use.

### ~~Step 4: Set Anthropic API Key~~ (NO LONGER NEEDED!)

**Phase 5 AI features now work through Claude skill invocation - no API key required!**

When you invoke the gslides skill through Claude Code, Claude generates AI content directly:
- **No API key setup needed**
- **No external API costs**
- **No configuration required**

Simply use the skill through Claude Code and Claude will generate content in real-time.

## Authentication

### OAuth 2.0 Flow

The skill uses OAuth 2.0 for Google API authentication:

1. **First Run**: Opens browser for user consent
2. **Subsequent Runs**: Uses saved token from `auth/token.json`
3. **Token Refresh**: Automatic when token expires

### Manual Token Reset

```bash
# Delete expired token
rm auth/token.json

# Re-authenticate
python examples/test_auth.py
```

### Service Account (Advanced)

For server environments without browser access:

1. Create service account in Google Cloud Console
2. Download service account key JSON
3. Share presentations with service account email
4. Use service account credentials instead of OAuth

See `auth/oauth_setup.md` for detailed setup instructions.

## Core Features

### Phase 1: Foundation

**Create, read, and analyze presentations**

```python
# Create presentation
result = editor.create_presentation('Q4 Results')
pres_id = result['pres_id']

# Analyze structure
analysis = editor.analyze_presentation(pres_id)
print(f"Slides: {analysis.slide_count}")
for slide in analysis.slides:
    print(f"  Slide {slide['slide_number']}: {slide['element_count']} elements")

# Read text content
text = editor.read_presentation_text(pres_id)
print(text)

# Print formatted structure
editor.print_presentation_structure(pres_id)
```

**Examples**: `examples/test_auth.py`, `examples/test_create.py`

### Phase 2: Creation Basics

**Build presentations with slides, text, shapes, and layouts**

```python
# Create slide with layout
slide = editor.create_slide(pres_id, layout_id='TITLE_AND_BODY', index=1)

# Add text box
editor.insert_text_box(
    pres_id, slide['slide_id'],
    text='Welcome to Q4 Results',
    x=50, y=50, width=620, height=80
)

# Add shape
editor.insert_shape(
    pres_id, slide['slide_id'],
    shape_type='RECTANGLE',
    x=100, y=200, width=500, height=150
)

# Style text
editor.update_text_style(pres_id, text_box_id, {
    'bold': True,
    'fontSize': {'magnitude': 24, 'unit': 'PT'},
    'foregroundColor': {'red': 0.2, 'green': 0.3, 'blue': 0.8}
})

# Batch operations
requests = [
    {'createSlide': {'insertionIndex': 0}},
    # ... more requests
]
editor.batch_update(pres_id, requests)
```

**Coordinate System**: Points (1 inch = 72 points), default slide 720x405pt, origin at top-left (0,0)

**Examples**: `examples/basic_creation.py`, `examples/layout_demo.py`

### Phase 3: Visual Design

**Apply brand guidelines, themes, and WCAG-compliant design**

```python
# Load brand guidelines
brand = editor.load_brand_guidelines('brand_templates/corporate_brand.json')

# Apply brand theme
result = editor.apply_brand_theme(pres_id, brand)
print(f"Applied to {result['slides_updated']} slides")

# Validate compliance
validation = editor.validate_brand_compliance(pres_id, brand)
print(f"Brand compliance: {validation['compliance_score']}%")

# Set slide background
editor.set_slide_background(pres_id, slide_id, '#F5F5F5')

# Apply design system
from scripts.visual_composer import DesignTokens
tokens = DesignTokens.default()
editor.apply_design_system(pres_id, tokens)

# Validate accessibility
contrast = editor.validate_contrast('#333333', '#FFFFFF', font_size=16)
if contrast['passes']:
    print(f"WCAG AA compliant: {contrast['ratio']:.2f}:1")

# Get visual hierarchy
hierarchy = editor.get_visual_hierarchy(levels=3)
for level in hierarchy:
    print(f"H{level['level']}: {level['font_size']}pt, {level['weight']}")
```

**Brand Guidelines Format**: JSON with colors, fonts, logo specs, spacing rules

**Examples**: `examples/brand_application.py`, `examples/visual_hierarchy.py`, `examples/accessibility_demo.py`

### Phase 4: Data Visualization

**Create charts, tables, and images following Analytics Reporter principles**

```python
# Create bar chart
data = {
    'categories': ['Q1', 'Q2', 'Q3', 'Q4'],
    'series': [
        {'name': 'Revenue', 'values': [100, 150, 175, 200]},
        {'name': 'Profit', 'values': [20, 35, 45, 60]}
    ]
}
position = {'x': 100, 'y': 150, 'width': 500, 'height': 300}
chart = editor.create_chart(pres_id, slide_id, 'BAR_CHART', data, position)

# Create table
table_data = [
    ['Metric', 'Q3', 'Q4', 'Change'],
    ['Revenue', '$1.5M', '$2.0M', '+33%'],
    ['Users', '10K', '15K', '+50%']
]
table = editor.create_table(pres_id, slide_id, table_data, position)

# Insert image
image = editor.insert_image(
    pres_id, slide_id,
    image_source='https://example.com/chart.png',
    position={'x': 50, 'y': 100, 'width': 600, 'height': 300}
)
```

**Chart Types**: BAR_CHART, LINE_CHART, PIE_CHART, COLUMN_CHART, AREA_CHART, SCATTER_CHART

**Image Sources**: URL, local file path, or Google Drive file ID

**Examples**: `examples/charts_demo.py`, `examples/tables_demo.py`, `examples/images_demo.py`, `examples/analytics_reporter_style.py`

### Phase 5: Intelligent Content

**AI-powered content generation, story arc, and personality injection**

```python
# Generate from notes
notes = """
Product roadmap Q1: Performance issues causing 3-5s load times.
Implemented caching, reduced to 800ms. Customer satisfaction up 40%.
Next: Mobile optimization, AI features in Q2.
"""

result = editor.generate_from_notes(
    notes=notes,
    purpose='executive_update',
    audience='C-suite and product stakeholders'
)
print(f"Created {result['slide_count']} slides: {result['pres_url']}")

# Apply story arc
arc_result = editor.apply_story_arc(
    result['pres_id'],
    content_blocks=result['content_blocks'],
    audience='C-suite executives'
)
print(f"Arc score: {arc_result['arc_score']}/100")

# Add personality
whimsy = editor.add_whimsy(pres_id, personality_level='moderate')
print(f"Enhanced {whimsy['slides_enhanced']} slides")

# Generate speaker notes
notes_result = editor.generate_speaker_notes(pres_id, detail_level='moderate')
print(f"Presentation time: {notes_result['estimated_presentation_time']}")

# Improve narrative flow
flow_result = editor.improve_narrative_flow(pres_id)
print(f"Flow improved from {flow_result['before_score']} to {flow_result['after_score']}")

# Synthesize single slide
content = editor.synthesize_slide_content(
    slide_purpose='competitive_advantage',
    context={'key_points': ['Fast', 'Secure', 'Easy']},
    style='professional'
)
```

**Story Arc Stages**: Hook → Context → Challenge → Resolution → Benefits → Call to Action

**Personality Levels**: minimal (conservative), moderate (balanced), generous (bold)

**Examples**: `examples/ai_generation.py`, `examples/story_arc_demo.py`, `examples/personality_injection.py`, `examples/speaker_notes_generation.py`

### Phase 6: Quality & Polish

**Quality checks, collaboration, attribution, and production validation**

```python
# Run quality check
quality = editor.check_quality(pres_id, comprehensive=True)
print(f"Overall quality: {quality['overall_score']}/100")
for issue in quality['issues']:
    print(f"  {issue['severity']}: {issue['description']}")

# Add comment
editor.add_comment(
    pres_id,
    slide_index=2,
    text='Consider adding data source reference',
    author='Reviewer'
)

# Add attribution
sources = [
    {'title': 'Q4 Sales Data', 'url': 'https://internal.com/sales'},
    {'title': 'Customer Survey', 'date': '2024-01-15'}
]
editor.add_attribution(pres_id, sources)

# Validate for production
validation = editor.validate_for_production(pres_id)
if validation['ready']:
    print("Ready to publish!")
else:
    print(f"Issues to fix: {len(validation['issues'])}")
    for issue in validation['issues']:
        print(f"  - {issue['description']}")
```

**Quality Checks**: Accessibility, brand compliance, data accuracy, layout consistency

**Examples**: `examples/quality_validation.py`, `examples/collaboration_workflow.py`

## API Reference

### Core Classes

- **GoogleSlidesEditor**: Main API interface
- **PresentationAnalysis**: Presentation structure analysis
- **BrandGuidelines**: Brand configuration
- **DesignTokens**: Design system tokens

### Phase 1: Foundation Methods

- `create_presentation(title)` - Create new presentation
- `get_presentation(pres_url_or_id)` - Get presentation data
- `analyze_presentation(pres_url_or_id)` - Analyze structure
- `read_presentation_text(pres_url_or_id)` - Extract text
- `print_presentation_structure(pres_url_or_id)` - Print formatted structure

### Phase 2: Creation Methods

- `create_slide(pres_id, layout_id, index)` - Create slide
- `delete_slide(pres_id, slide_id)` - Delete slide
- `duplicate_slide(pres_id, slide_id)` - Duplicate slide
- `get_slide(pres_id, slide_id)` - Get slide details
- `insert_text_box(pres_id, slide_id, text, x, y, width, height)` - Add text box
- `insert_shape(pres_id, slide_id, shape_type, x, y, width, height)` - Add shape
- `update_text_style(pres_id, object_id, style_dict)` - Style text
- `batch_update(pres_id, requests)` - Execute batch operations

### Phase 3: Visual Design Methods

- `apply_theme(pres_id, theme_config)` - Apply theme
- `set_slide_background(pres_id, slide_id, color)` - Set background
- `apply_design_system(pres_id, design_tokens)` - Apply design system
- `load_brand_guidelines(filepath)` - Load brand JSON
- `apply_brand_theme(pres_id, brand, slide_ids)` - Apply brand
- `validate_brand_compliance(pres_id, brand)` - Validate brand
- `validate_contrast(text_color, bg_color, font_size, is_bold)` - WCAG validation
- `get_visual_hierarchy(levels)` - Get hierarchy levels

### Phase 4: Data Visualization Methods

- `create_chart(pres_id, slide_id, chart_type, data, position, style)` - Create chart
- `create_table(pres_id, slide_id, data, position, style)` - Create table
- `insert_image(pres_id, slide_id, image_source, position)` - Insert image

### Phase 5: Intelligent Content Methods (No API Key Required!)

- `generate_from_notes(notes, purpose, audience, brand_guidelines)` - Generate presentation
- `apply_story_arc(presentation_id, content_blocks, audience)` - Apply narrative
- `add_whimsy(presentation_id, personality_level)` - Add personality
- `synthesize_slide_content(slide_purpose, context, style)` - Generate slide
- `improve_narrative_flow(presentation_id)` - Improve flow
- `generate_speaker_notes(presentation_id, detail_level)` - Generate notes

**Note**: Phase 5 works through Claude skill invocation. No `api_key` parameter needed!

### Phase 6: Quality & Polish Methods

- `check_quality(presentation_id, comprehensive)` - Run quality checks
- `add_comment(presentation_id, slide_index, text, author)` - Add comment
- `add_attribution(presentation_id, sources)` - Add attribution
- `validate_for_production(presentation_id)` - Pre-publish validation

See detailed API documentation in `docs/api/` for complete parameter specifications and return types.

## Examples

All examples are in the `examples/` directory with working code:

### Foundation
- `test_auth.py` - Test OAuth authentication
- `test_create.py` - Create and analyze presentations
- `basic_creation.py` - Slides, text, shapes basics

### Design
- `layout_demo.py` - Layout management
- `brand_application.py` - Brand guidelines application
- `visual_hierarchy.py` - Visual hierarchy demonstration
- `accessibility_demo.py` - WCAG accessibility validation

### Data Visualization
- `charts_demo.py` - Chart creation examples
- `tables_demo.py` - Table formatting
- `images_demo.py` - Image insertion
- `analytics_reporter_style.py` - Analytics Reporter principles

### AI Content
- `ai_generation.py` - AI-powered content generation
- `story_arc_demo.py` - Story arc application
- `personality_injection.py` - Personality enhancement
- `speaker_notes_generation.py` - Auto-generate speaker notes

### Quality
- `quality_validation.py` - Comprehensive quality checks
- `collaboration_workflow.py` - Comments and attribution

Each example includes:
- Clear documentation of what it demonstrates
- Working code that can be run immediately
- Expected output examples
- Common variations and use cases

## Best Practices

### When to Use Each Phase

**Phase 1 (Foundation)**: Reading existing presentations, extracting data, analysis
**Phase 2 (Creation)**: Manual layout control, custom designs, precise positioning
**Phase 3 (Visual Design)**: Brand compliance, accessibility requirements, design systems
**Phase 4 (Data Viz)**: Reports, dashboards, data-heavy presentations
**Phase 5 (AI Content)**: Rapid prototyping, content generation, narrative optimization
**Phase 6 (Quality)**: Pre-publication review, collaboration, production readiness

### Common Patterns

**Template + AI Content**:
```python
# Create base with brand
brand = editor.load_brand_guidelines('corporate_brand.json')
result = editor.create_presentation('Q4 Results')
editor.apply_brand_theme(result['pres_id'], brand)

# Generate content
content_result = editor.generate_from_notes(notes, 'executive_update', 'C-suite')

# Combine: branded template + AI content
```

**Data Visualization Pipeline**:
```python
# 1. Create chart from data
# 2. Apply brand colors
# 3. Validate accessibility
# 4. Add attribution
```

**Quality Workflow**:
```python
# 1. Generate presentation
# 2. Run quality check
# 3. Fix identified issues
# 4. Validate for production
# 5. Publish
```

### Performance Optimization

- Use `batch_update()` for multiple operations (single API call)
- Cache `BrandGuidelines` objects (reuse across presentations)
- Limit AI calls (expensive, use strategically)
- Process images before upload (resize, optimize)

### Error Handling

```python
from googleapiclient.errors import HttpError

try:
    result = editor.create_presentation('Test')
except HttpError as e:
    if e.resp.status == 403:
        print("Permission denied - check OAuth scopes")
    elif e.resp.status == 429:
        print("Rate limit - wait and retry")
    else:
        raise
```

## Troubleshooting

### OAuth Issues

**Error: `credentials.json not found`**
- Download OAuth credentials from Google Cloud Console
- Place in `auth/credentials.json`

**Error: `invalid_grant` or token expired**
- Delete `auth/token.json`
- Re-run `python examples/test_auth.py`

**Browser doesn't open**
- Check firewall settings
- Try manual URL from console output

### API Errors

**Error: 403 Forbidden**
- Verify API is enabled in Google Cloud Console
- Check OAuth scopes in `auth_manager.py`
- Ensure user has access to presentation

**Error: 404 Not Found**
- Verify presentation ID is correct
- PowerPoint files (.pptx) cannot be edited via Slides API

**Error: 429 Rate Limit**
- Reduce request frequency
- Implement exponential backoff
- Consider quota increase request

### AI Generation Issues

**~~Error: `ANTHROPIC_API_KEY not set`~~ (NO LONGER NEEDED!)**
- Phase 5 now works through Claude skill invocation
- No API key configuration required
- Simply use the skill through Claude Code

**Poor content quality**
- Provide more context in `notes` parameter
- Be specific about `audience` (not just "executives")
- Adjust `personality_level` for context
- Review and iterate on output

**High API costs**
- Use AI features strategically (not every slide)
- Cache results when possible
- Start with `minimal` personality level
- Generate outline first, then expand

## Cost Considerations

### Google Slides API

- **Free tier**: 300 requests/minute per user
- **Costs**: Free for most use cases
- **Quotas**: Can be increased via Google Cloud Console

### ~~Anthropic API~~ Phase 5: AI Features (FREE!)

**Phase 5 AI features are now completely FREE** - works through Claude skill invocation:
- **No external API costs**
- **No token usage tracking needed**
- **No API key management**
- **Simply use through Claude Code**

### Optimization Strategies

1. **Batch Operations**: Combine multiple Google Slides API updates into single call
2. **Selective AI**: Use AI for complex content, templates for standard slides
3. **Content Reuse**: Build library of tested prompts and patterns
4. **Progressive Enhancement**: Generate basic content, enhance selectively

**Note**: Only Google Slides API calls have costs/quotas. Phase 5 AI features are free!

## Contributing

### Extending the Skill

Add new features by:

1. Create module in `scripts/` (e.g., `custom_feature.py`)
2. Import in `gslides_editor.py`
3. Add methods to `GoogleSlidesEditor` class
4. Create example in `examples/`
5. Update documentation

### Module Structure

```python
# scripts/custom_feature.py
class CustomFeature:
    def __init__(self, slides_service):
        self.slides_service = slides_service

    def do_something(self, pres_id, params):
        # Implementation
        return result
```

### Testing

```bash
# Run all examples
python examples/test_auth.py
python examples/basic_creation.py
# ... etc

# Test specific feature
python examples/your_feature_demo.py
```

### Documentation

Update these files when adding features:
- `SKILL.md` (this file) - Overview and examples
- `docs/api/` - Detailed API documentation
- `examples/` - Working code examples
- `TESTING.md` - Test coverage

## License

MIT License - See LICENSE file for details

## Support

- **Documentation**: See `docs/` directory
- **Examples**: See `examples/` directory
- **Issues**: Create GitHub issue with reproduction steps
- **Questions**: Discussions in GitHub repository

## Roadmap

### Planned Features

- **Animation Support**: Add slide transitions and element animations
- **Master Slide Management**: Create and modify master slides programmatically
- **Video Integration**: Embed and position videos
- **Real-time Collaboration**: Live editing with conflict resolution
- **Template Library**: Pre-built templates for common use cases
- **Export Options**: PDF, PNG, video export
- **Advanced AI**: Multi-modal content (image generation, chart AI)

### Version History

- **v1.0**: Foundation + Creation (Phases 1-2)
- **v2.0**: Visual Design + Data Viz (Phases 3-4)
- **v3.0**: Intelligent Content (Phase 5)
- **v4.0**: Quality & Polish (Phase 6) - Current

## Acknowledgments

Built on:
- Google Slides API v1
- Anthropic Claude API
- Python Google API Client
- Analytics Reporter design principles
- WCAG 2.1 accessibility guidelines
