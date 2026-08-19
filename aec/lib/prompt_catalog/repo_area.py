"""Catalogued prompts for ``aec repo setup`` / ``aec repo prune``.

Repo setup is the longest interactive flow in the CLI — Raycast scripts, lint
hook mode, language selection, git essentials, commit strategy, discovery
scan. None are org-overlay-eligible (they describe one repo's local state),
but every one is catalogued so an agent can drive a full repo setup with
``--answers``.
"""
from __future__ import annotations

from .spec import DynamicPromptFamily, PromptSpec

REPO_RAYCAST_GENERATE = "repo.raycast.generate"
REPO_RAYCAST_LAUNCHERS = "repo.raycast.launchers"
REPO_HOOKS_MODE = "repo.hooks.mode"
REPO_HOOKS_LANGUAGES = "repo.hooks.languages"
REPO_TEST_SUITES_SELECTION = "repo.test_suites.selection"
REPO_GIT_USE_GITHUB = "repo.git.use_github"
REPO_GIT_RUN_INIT = "repo.git.run_init"
REPO_GIT_ESSENTIALS = "repo.git.essentials"
REPO_GIT_COMMIT_STRATEGY = "repo.git.commit_strategy"
REPO_SETUP_PROJECT_PATH = "repo.setup.project_path"
REPO_SETUP_EXISTING_ACTION = "repo.setup.existing_action"
REPO_SETUP_CREATE_DIRECTORY = "repo.setup.create_directory"
REPO_DISCOVER_SCAN = "repo.discover.scan"
REPO_PRUNE_CONFIRM = "repo.prune.confirm"

# Concrete ID appends the agent key whose hook config already exists.
REPO_HOOKS_EXISTING_CONFIG_PREFIX = "repo.hooks.existing_config"

SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        REPO_RAYCAST_GENERATE,
        command="repo setup",
        summary="Generate Raycast scripts for the agents detected in this repo.",
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        REPO_RAYCAST_LAUNCHERS,
        command="repo setup",
        summary="Create Raycast launcher scripts for this project.",
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        REPO_HOOKS_MODE,
        command="repo setup",
        summary=(
            "Lint hook mode: 1 auto (all detected languages), 2 per-repo (ask "
            "per project), 3 never."
        ),
        type="enum[1,2,3]",
        default="1",
        choices=("1", "2", "3"),
    ),
    PromptSpec(
        REPO_HOOKS_LANGUAGES,
        command="repo setup",
        summary=(
            "Which detected language to install lint hooks for, by menu number. "
            "'all' selects every detected language; 'none' skips lint hooks."
        ),
        type="string",
        default="all",
    ),
    PromptSpec(
        REPO_TEST_SUITES_SELECTION,
        command="repo setup",
        summary=(
            "Which detected test suites to record in .aec.json: comma-separated "
            "menu numbers, 'all', or 'none'."
        ),
        type="string",
        default="all",
    ),
    PromptSpec(
        REPO_GIT_USE_GITHUB,
        command="repo setup",
        summary="No git remote was detected — does this project intend to use GitHub?",
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        REPO_GIT_RUN_INIT,
        command="repo setup",
        summary="Let AEC run `git init` in this project.",
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        REPO_GIT_ESSENTIALS,
        command="repo setup",
        summary=(
            "Which missing git essentials AEC should create: comma-separated "
            "menu numbers, 'all', or 'none'."
        ),
        type="string",
        default="all",
    ),
    PromptSpec(
        REPO_GIT_COMMIT_STRATEGY,
        command="repo setup",
        summary=(
            "How AEC commits the files it created: 1 one commit at the end, "
            "2 incremental per file, 3 stage only, 4 no git operations."
        ),
        type="enum[1,2,3,4]",
        default="1",
        choices=("1", "2", "3", "4"),
    ),
    PromptSpec(
        REPO_SETUP_PROJECT_PATH,
        command="repo setup",
        summary=(
            "Project name or path to set up. Same value as the positional "
            "argument; an empty answer aborts."
        ),
        type="string",
    ),
    PromptSpec(
        REPO_SETUP_EXISTING_ACTION,
        command="repo setup",
        summary=(
            "This repo was set up before: 1 check for updates, 2 fresh setup "
            "(skip existing files), 3 cancel."
        ),
        type="enum[1,2,3]",
        default="1",
        choices=("1", "2", "3"),
    ),
    PromptSpec(
        REPO_SETUP_CREATE_DIRECTORY,
        command="repo setup",
        summary="The project could not be cloned — create a new empty directory instead.",
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        REPO_DISCOVER_SCAN,
        command="repo setup",
        summary="Scan the project for files matching items in the AEC catalog.",
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        REPO_PRUNE_CONFIRM,
        command="repo prune",
        summary="Remove the listed stale entries from the tracking file. Same as --yes.",
        type="yes_no",
        default=False,
    ),
)

FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        REPO_HOOKS_EXISTING_CONFIG_PREFIX,
        command="repo setup",
        summary=(
            "One agent already has a hook config: 1 skip, 2 merge hooks into it, "
            "3 show the config without writing. The concrete ID appends the agent key."
        ),
        type="enum[1,2,3]",
    ),
)
