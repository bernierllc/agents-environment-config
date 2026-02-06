#!/bin/bash
# Test script for agent-tools setup, migration, and rollback
# Creates isolated test environments to verify the scripts work correctly
#
# Usage: ./scripts/test-agent-tools-setup.sh [test-name]
#   test-name: fresh | old-structure | old-with-content | idempotent | rollback | parity | all
#
# IMPORTANT: This creates temporary directories and does NOT affect your real ~/.claude or ~/.cursor

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Test environment base
TEST_BASE="/tmp/agent-tools-test-$$"
TEST_HOME="$TEST_BASE/home"

# Track test results
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Save real HOME
REAL_HOME="$HOME"

# --- Helper Functions ---

setup_test_env() {
    local test_name="$1"
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  TEST: $test_name${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"

    # Clean up any previous test
    rm -rf "$TEST_BASE"
    mkdir -p "$TEST_HOME"
    mkdir -p "$TEST_HOME/.claude"
    mkdir -p "$TEST_HOME/.cursor"

    TESTS_RUN=$((TESTS_RUN + 1))
}

# Run a script with TEST_HOME as HOME
run_script() {
    local script="$1"
    shift
    HOME="$TEST_HOME" bash "$script" "$@"
}

cleanup_test_env() {
    # Nothing to do - HOME was never changed in parent
    :
}

pass() {
    echo -e "  ${GREEN}✓ PASS${NC}: $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo -e "  ${RED}✗ FAIL${NC}: $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

assert_symlink_exists() {
    local path="$1"
    local description="$2"
    if [ -L "$path" ]; then
        pass "$description exists as symlink"
    else
        fail "$description should be a symlink"
    fi
}

assert_symlink_target() {
    local path="$1"
    local expected_pattern="$2"
    local description="$3"
    if [ -L "$path" ]; then
        local actual=$(readlink "$path")
        if [[ "$actual" == *"$expected_pattern"* ]]; then
            pass "$description points to correct target"
        else
            fail "$description should contain '$expected_pattern', got '$actual'"
        fi
    else
        fail "$description is not a symlink"
    fi
}

assert_file_exists() {
    local path="$1"
    local description="$2"
    if [ -f "$path" ]; then
        pass "$description exists"
    else
        fail "$description should exist"
    fi
}

assert_dir_exists() {
    local path="$1"
    local description="$2"
    if [ -d "$path" ]; then
        pass "$description exists"
    else
        fail "$description should exist"
    fi
}

assert_not_exists() {
    local path="$1"
    local description="$2"
    if [ ! -e "$path" ]; then
        pass "$description does not exist (expected)"
    else
        fail "$description should not exist"
    fi
}

# --- Test 1: Fresh Install ---
test_fresh_install() {
    setup_test_env "Fresh Install (no existing directories)"

    echo "Running setup-agent-tools.sh..."
    run_script "$SCRIPT_DIR/setup-agent-tools.sh" 2>&1 | head -50

    echo -e "\n${BLUE}Verifying results...${NC}\n"

    # Check ~/.agent-tools/ structure
    assert_dir_exists "$TEST_HOME/.agent-tools" "~/.agent-tools/"
    assert_file_exists "$TEST_HOME/.agent-tools/.aec-managed" ".aec-managed marker"
    assert_dir_exists "$TEST_HOME/.agent-tools/rules" "~/.agent-tools/rules/"
    assert_dir_exists "$TEST_HOME/.agent-tools/agents" "~/.agent-tools/agents/"
    assert_dir_exists "$TEST_HOME/.agent-tools/skills" "~/.agent-tools/skills/"
    assert_dir_exists "$TEST_HOME/.agent-tools/commands" "~/.agent-tools/commands/"

    # Check repo symlinks in ~/.agent-tools/
    assert_symlink_exists "$TEST_HOME/.agent-tools/rules/agents-environment-config" "~/.agent-tools/rules/agents-environment-config"
    assert_symlink_target "$TEST_HOME/.agent-tools/rules/agents-environment-config" ".agent-rules" "rules symlink"

    cleanup_test_env
}

# --- Test 2: Old Structure Detection ---
test_old_structure() {
    setup_test_env "Old Structure (symlinks to repo)"

    echo "Creating old-style symlinks..."
    mkdir -p "$TEST_HOME/.claude/agents"
    mkdir -p "$TEST_HOME/.claude/skills"
    mkdir -p "$TEST_HOME/.cursor/rules"
    mkdir -p "$TEST_HOME/.cursor/commands"

    # Create old-style symlinks (directly to repo)
    ln -s "$REPO_ROOT/.claude/agents" "$TEST_HOME/.claude/agents/agents-environment-config"
    ln -s "$REPO_ROOT/.claude/skills" "$TEST_HOME/.claude/skills/agents-environment-config"
    ln -s "$REPO_ROOT/.cursor/rules" "$TEST_HOME/.cursor/rules/agents-environment-config"
    ln -s "$REPO_ROOT/.cursor/commands" "$TEST_HOME/.cursor/commands/agents-environment-config"

    echo "Running migration with --dry-run..."
    run_script "$SCRIPT_DIR/migrate-to-agent-tools.sh" --dry-run 2>&1 | head -80

    echo -e "\n${BLUE}Verifying dry-run didn't change anything...${NC}\n"

    # Verify old symlinks still exist (dry-run shouldn't change them)
    assert_symlink_exists "$TEST_HOME/.claude/agents/agents-environment-config" "Old Claude agents symlink"
    assert_not_exists "$TEST_HOME/.agent-tools" "~/.agent-tools/ (should not exist after dry-run)"

    echo -e "\n${BLUE}Running actual migration...${NC}\n"
    echo "y" | run_script "$SCRIPT_DIR/migrate-to-agent-tools.sh" 2>&1 | head -80

    echo -e "\n${BLUE}Verifying migration results...${NC}\n"

    # Check new structure
    assert_dir_exists "$TEST_HOME/.agent-tools" "~/.agent-tools/"
    assert_symlink_exists "$TEST_HOME/.agent-tools/rules/agents-environment-config" "~/.agent-tools/rules/agents-environment-config"
    assert_symlink_target "$TEST_HOME/.agent-tools/rules/agents-environment-config" ".agent-rules" "rules symlink"

    # Check agent-specific symlinks point through ~/.agent-tools/
    assert_symlink_target "$TEST_HOME/.claude/agents/agents-environment-config" ".agent-tools" "Claude agents symlink"
    assert_symlink_target "$TEST_HOME/.claude/skills/agents-environment-config" ".agent-tools" "Claude skills symlink"

    cleanup_test_env
}

# --- Test 3: Old Structure with User Content ---
test_old_with_user_content() {
    setup_test_env "Old Structure with User Content"

    echo "Creating old-style structure with user content..."
    mkdir -p "$TEST_HOME/.claude/agents"
    mkdir -p "$TEST_HOME/.claude/skills"
    mkdir -p "$TEST_HOME/.cursor/rules"

    # Create old-style symlinks
    ln -s "$REPO_ROOT/.claude/agents" "$TEST_HOME/.claude/agents/agents-environment-config"
    ln -s "$REPO_ROOT/.claude/skills" "$TEST_HOME/.claude/skills/agents-environment-config"

    # Create user content
    echo "# My Custom Agent" > "$TEST_HOME/.claude/agents/my-agent.md"
    mkdir -p "$TEST_HOME/.claude/skills/my-skill"
    echo "# My Skill" > "$TEST_HOME/.claude/skills/my-skill/README.md"
    echo "# My Custom Rule" > "$TEST_HOME/.cursor/rules/my-rule.mdc"

    echo "Running migration..."
    echo "y" | run_script "$SCRIPT_DIR/migrate-to-agent-tools.sh" 2>&1 | head -80

    echo -e "\n${BLUE}Verifying user content was NOT moved...${NC}\n"

    # User content should still be in original locations
    assert_file_exists "$TEST_HOME/.claude/agents/my-agent.md" "User agent file"
    assert_dir_exists "$TEST_HOME/.claude/skills/my-skill" "User skill directory"
    assert_file_exists "$TEST_HOME/.cursor/rules/my-rule.mdc" "User rule file"

    # User content should NOT be in ~/.agent-tools/
    assert_not_exists "$TEST_HOME/.agent-tools/agents/my-agent.md" "User agent (should NOT be moved)"
    assert_not_exists "$TEST_HOME/.agent-tools/skills/my-skill" "User skill (should NOT be moved)"

    cleanup_test_env
}

# --- Test 4: Idempotency ---
test_idempotency() {
    setup_test_env "Idempotency (run setup multiple times)"

    echo "Running setup-agent-tools.sh first time..."
    run_script "$SCRIPT_DIR/setup-agent-tools.sh" 2>&1 | head -30

    echo -e "\n${BLUE}Running setup-agent-tools.sh second time...${NC}\n"
    run_script "$SCRIPT_DIR/setup-agent-tools.sh" 2>&1 | head -30

    echo -e "\n${BLUE}Verifying idempotency...${NC}\n"

    # Structure should still exist
    assert_dir_exists "$TEST_HOME/.agent-tools" "~/.agent-tools/"
    assert_symlink_exists "$TEST_HOME/.agent-tools/rules/agents-environment-config" "rules symlink"

    # Symlinks should still point to correct targets
    assert_symlink_target "$TEST_HOME/.agent-tools/rules/agents-environment-config" ".agent-rules" "rules symlink"

    pass "Setup can be run multiple times safely"

    cleanup_test_env
}

# --- Test 5: Rollback ---
test_rollback() {
    setup_test_env "Rollback"

    echo "Creating old-style structure..."
    mkdir -p "$TEST_HOME/.claude/agents"
    mkdir -p "$TEST_HOME/.claude/skills"
    ln -s "$REPO_ROOT/.claude/agents" "$TEST_HOME/.claude/agents/agents-environment-config"
    ln -s "$REPO_ROOT/.claude/skills" "$TEST_HOME/.claude/skills/agents-environment-config"

    echo "Running migration..."
    echo "y" | run_script "$SCRIPT_DIR/migrate-to-agent-tools.sh" 2>&1 | head -50

    # Find the backup directory
    BACKUP_DIR=$(ls -d "$TEST_HOME"/.agent-tools-backup-* 2>/dev/null | head -1)

    if [ -z "$BACKUP_DIR" ]; then
        fail "Backup directory was not created"
        cleanup_test_env
        return
    fi

    echo -e "\n${BLUE}Backup created at: $BACKUP_DIR${NC}\n"
    assert_file_exists "$BACKUP_DIR/symlinks.txt" "symlinks.txt backup"

    echo "Running rollback..."
    echo "y" | run_script "$SCRIPT_DIR/rollback-agent-tools.sh" "$BACKUP_DIR" 2>&1 | head -50

    echo -e "\n${BLUE}Verifying rollback results...${NC}\n"

    # ~/.agent-tools/ should be removed
    assert_not_exists "$TEST_HOME/.agent-tools" "~/.agent-tools/ (should be removed)"

    # Old symlinks should be restored (pointing to repo, not ~/.agent-tools/)
    assert_symlink_exists "$TEST_HOME/.claude/agents/agents-environment-config" "Restored Claude agents symlink"

    # Verify restored symlinks point to repo (not ~/.agent-tools/)
    local restored_target=$(readlink "$TEST_HOME/.claude/agents/agents-environment-config")
    if [[ "$restored_target" != *".agent-tools"* ]]; then
        pass "Restored symlink points to repo (not ~/.agent-tools/)"
    else
        fail "Restored symlink should point to repo, not ~/.agent-tools/"
    fi

    cleanup_test_env
}

# --- Test 6: Rule Parity Validation ---
test_rule_parity() {
    setup_test_env "Rule Parity Validation"

    echo "Running validate-rule-parity.py..."
    if python3 "$SCRIPT_DIR/validate-rule-parity.py"; then
        pass "Rule parity validation passes"
    else
        fail "Rule parity validation failed"
    fi

    # Test that it fails when .agent-rules/ is missing a file
    echo -e "\n${BLUE}Testing validation failure detection...${NC}\n"

    # Temporarily rename a file
    if [ -f "$REPO_ROOT/.agent-rules/general/architecture.md" ]; then
        mv "$REPO_ROOT/.agent-rules/general/architecture.md" "$REPO_ROOT/.agent-rules/general/architecture.md.bak"

        if python3 "$SCRIPT_DIR/validate-rule-parity.py" 2>&1 | grep -q "Missing"; then
            pass "Validation correctly detects missing files"
        else
            fail "Validation should detect missing files"
        fi

        # Restore the file
        mv "$REPO_ROOT/.agent-rules/general/architecture.md.bak" "$REPO_ROOT/.agent-rules/general/architecture.md"
    fi

    cleanup_test_env
}

# --- Run Tests ---

run_all_tests() {
    test_fresh_install
    test_old_structure
    test_old_with_user_content
    test_idempotency
    test_rollback
    test_rule_parity
}

# Parse arguments
TEST_TO_RUN="${1:-all}"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Agent Tools Setup Test Suite                           ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Test environment: $TEST_BASE"
echo "Repository: $REPO_ROOT"
echo ""

case "$TEST_TO_RUN" in
    fresh)
        test_fresh_install
        ;;
    old-structure)
        test_old_structure
        ;;
    old-with-content)
        test_old_with_user_content
        ;;
    idempotent)
        test_idempotency
        ;;
    rollback)
        test_rollback
        ;;
    parity)
        test_rule_parity
        ;;
    all)
        run_all_tests
        ;;
    *)
        echo "Unknown test: $TEST_TO_RUN"
        echo "Available tests: fresh, old-structure, old-with-content, idempotent, rollback, parity, all"
        exit 1
        ;;
esac

# Summary
echo -e "\n${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Test Summary                                            ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Tests run: ${CYAN}$TESTS_RUN${NC}"
echo -e "Passed:    ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed:    ${RED}$TESTS_FAILED${NC}"
echo ""

# Cleanup
rm -rf "$TEST_BASE"
echo "Test environment cleaned up."

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "\n${RED}Some tests failed!${NC}"
    exit 1
else
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
fi
