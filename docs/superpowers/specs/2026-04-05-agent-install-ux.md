# Interactive Agent Install UX

> Design spec for the interactive install experience when running
> `aec install agent` without a name. Supports browse-by-division,
> keyword search, and preset bundles.

## Problem

With 184 agents across 14 divisions, the old numbered-list approach
(scroll through everything, pick by number) is unusable. Users need
multiple ways to discover and install agents depending on their intent:

- **"I know what I want"** -- `aec install agent testing-architect` (already works)
- **"Show me what's in testing"** -- browse by division
- **"I need something for frontend"** -- keyword search
- **"Give me the standard engineering setup"** -- preset bundle

## Core Principles

1. **Targeted install is unchanged.** `aec install agent <name>` works exactly
   as before. Interactive mode only triggers when name is omitted.
2. **All three modes in one session.** After installing from browse, the user
   can search or try bundles without re-running the command.
3. **Same scope rules apply.** `-g` flag, not-in-repo errors, manifest tracking
   all work the same as targeted install. The `*` installed marker checks the
   same scope that will be installed to (local by default, global if `-g`).
4. **Bundles are data, not code.** Defined in a JSON file in the agents submodule.

---

## Interactive Mode Entry

**TTY check**: If stdin is not a TTY, error with
"Interactive mode requires a terminal. Use `aec install agent <name>` instead."

**`--yes` flag**: Ignored in interactive mode. `--yes` only applies to targeted
installs where a specific name is given. Interactive mode always prompts.

When `aec install agent` is run without a name (counts computed at runtime):

```
184 agents available across 14 divisions.

How would you like to browse?
  [b] Browse by division
  [s] Search by keyword
  [p] Install a preset bundle
  [q] Quit

>
```

After completing any action (install, skip, back), the user returns to this
menu. The session loops until the user quits.

---

## Mode B: Browse by Division

```
> b

Divisions:
   1. engineering          (29)    8. project-management   (8)
   2. marketing            (29)    9. sales                (8)
   3. specialized          (29)   10. paid-media            (7)
   4. game-development     (20)   11. security              (7)
   5. testing              (13)   12. product               (6)
   6. support               (9)   13. spatial-computing     (6)
   7. design                (8)   14. academic              (5)

Select division(s) or [a]ll divisions, [b]ack: 5

testing (13 agents):
   1. testing-architect              v1.1.0  Testing systems design
   2. testing-reality-checker        v1.1.0  Evidence-based certification
   3. testing-suite-fixer            v1.1.0  Runs full test suite
   ...

Install: [a]ll, [n]one, numbers (1,3,5-8), or [b]ack:
```

**Selecting multiple divisions** works with the same `1,3,5-8` syntax.
Agents from all selected divisions are shown together with a division
label column.

**Already-installed agents** are marked with a `*` suffix. The check uses
the same scope that will be installed to (local by default, global if `-g`):

```
   1. testing-architect              v1.1.0  Testing systems design  *
```

---

## Mode S: Search by Keyword

```
> s
Search: frontend

Results:
   1. engineering-frontend-developer   v1.2.0  Expert frontend developer
   2. engineering-frontend-tamagui     v1.2.0  Tamagui cross-platform UI

Install: [a]ll, [n]one, numbers (1,2), or [b]ack:
```

Search matches against agent name, description, and division (case-insensitive).
Searching "testing" finds agents in the testing division even if "testing" only
appears in the division field, not the name or description.

No results prints "No agents found for '<term>'" and returns to the menu.

---

## Mode P: Preset Bundles

```
> p

Preset bundles:
   1. engineering-core    (8)  Senior dev, frontend, backend, mobile, devops, ...
   2. quality-core        (6)  Testing architect, reality checker, suite fixer, ...
   3. product-core        (4)  Sprint prioritizer, feedback synthesizer, ...
   4. full-stack         (18)  Engineering + quality + product combined

Install bundle: number, [d]etails to expand, or [b]ack: d1

engineering-core (8 agents):
   1. engineering-senior-developer     v1.2.0
   2. engineering-frontend-developer   v1.2.0
   3. engineering-backend-architect    v1.2.0
   4. engineering-mobile-app-builder   v1.2.0
   5. engineering-devops-automator     v1.1.0
   6. engineering-rapid-prototyper     v1.1.0
   7. engineering-code-reviewer        v1.2.0
   8. engineering-database-migration-agent  v1.2.0

Install all 8? [Y/n]:
```

**`d<number>` expands a bundle** to show its contents before installing.
Selecting a number directly installs the bundle (with confirmation).
Agents already installed are skipped with a note.

### Bundle Definition Format

Bundles are defined in `.claude/agents/bundles.json` within the agents
submodule repo (`bernierllc/agency-agents`). Creating or updating bundles
requires a commit to that repo followed by a submodule pointer update in AEC.

```json
{
  "bundleVersion": 1,
  "bundles": [
    {
      "name": "engineering-core",
      "description": "Essential engineering agents for full-stack development",
      "agents": [
        "engineering-senior-developer",
        "engineering-frontend-developer",
        "engineering-backend-architect",
        "engineering-mobile-app-builder",
        "engineering-devops-automator",
        "engineering-rapid-prototyper",
        "engineering-code-reviewer",
        "engineering-database-migration-agent"
      ]
    },
    {
      "name": "quality-core",
      "description": "Testing and quality assurance agents",
      "agents": [
        "testing-architect",
        "testing-reality-checker",
        "testing-suite-fixer",
        "testing-evidence-collector",
        "testing-performance-benchmarker",
        "testing-accessibility-specialist"
      ]
    },
    {
      "name": "product-core",
      "description": "Product management and strategy agents",
      "agents": [
        "product-sprint-prioritizer",
        "product-feedback-synthesizer",
        "product-trend-researcher",
        "product-feature-alchemist"
      ]
    },
    {
      "name": "full-stack",
      "description": "Engineering + quality + product combined",
      "includes": ["engineering-core", "quality-core", "product-core"]
    }
  ]
}
```

**Key fields:**
- `agents` -- list of agent file stems (matches the filename without `.md`)
- `includes` -- compose bundles from other bundles (resolved recursively with
  seen-set for cycle protection, deduped)
- Missing agents (renamed/removed) are warned about but don't block the install
- Missing bundle references in `includes` are warned about and skipped

---

## Implementation Scope

### New files

| File | Purpose |
|---|---|
| `aec/lib/interactive_install.py` | Interactive install mode: menu loop, browse, search, bundles |
| `aec/lib/input_utils.py` | Extracted `parse_selection()` shared by skills.py and interactive_install.py |
| `tests/test_interactive_install.py` | Tests for all three modes + menu loop |
| `bundles.json` (in agents submodule) | Bundle definitions -- committed to `bernierllc/agency-agents` |

### Modified files

| File | Changes |
|---|---|
| `aec/commands/install_cmd.py` | When `name` is None for agent type, delegate to interactive mode |
| `aec/cli.py` | Change `name` from required to optional argument (`Optional[str] = None`) for the install command, in both typer and argparse modes |
| `aec/lib/sources.py` | Add `load_bundles(source_dir)` to read bundles.json |
| `aec/commands/skills.py` | Import `parse_selection` from `aec.lib.input_utils` instead of defining `_parse_selection` locally |

### Prior art

The `install_step()` function in `aec/commands/skills.py` (line 337) is the
skills-era interactive install with numbered selection. It works for ~30 skills
but doesn't scale to 184 agents. The new `interactive_install.py` is the
evolution of that pattern, adding division browsing, search, and bundles.
The `_parse_selection` helper from `skills.py` is extracted to a shared
utility rather than duplicated.

---

## Interaction with Existing Commands

| Command | Behavior |
|---|---|
| `aec install agent testing-architect` | Direct install (unchanged) |
| `aec install agent` | Enters interactive mode |
| `aec install agent -g` | Interactive mode, installs to global scope |
| `aec install agent -y` | Ignored -- interactive mode always prompts |
| `aec install skill` | Existing skill install (no changes -- skills are ~30, flat list is fine) |
| `aec search agent testing` | Non-interactive search (unchanged) |

---

## Edge Cases

- **No agents available**: Print "No agents found in source" and exit.
- **All agents already installed**: Show the menu but mark everything with `*`.
  User can still reinstall/upgrade via targeted `aec install agent <name>`.
- **Bundle references missing agent**: Warn `"engineering-foo not found, skipping"`
  and install the rest.
- **Bundle `includes` references missing bundle**: Warn `"bundle 'missing-name' not found, skipping"` and continue with other includes.
- **Bundle includes cycle**: Resolve with a seen-set, no infinite recursion.
- **EOF/Ctrl-C during interactive**: Clean exit, no partial state.
- **Non-interactive (piped input)**: If stdin is not a TTY, error with
  "Interactive mode requires a terminal. Use `aec install agent <name>` instead."
- **No bundles.json**: Preset bundle mode shows "No bundles defined" and returns to menu.

---

## Out of Scope

- **Custom user-defined bundles**: Users can't create their own bundles yet.
  They can install agents one at a time or use the provided presets.
- **Bundle versioning**: Bundles don't have versions. They reference agents
  by name; the agent versions are what get tracked.
- **Applying to skills/rules**: This interactive mode is agent-specific.
  Skills are ~30 items and work fine as a flat list. Rules don't have
  an interactive install yet.
