#!/bin/bash
# Ensure submodules are pushed to their remotes before parent push.
# Run from repo root. Exits 0 if all submodules are pushed; 1 if any need attention.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SUBMODULES=(".claude/agents" ".claude/skills")
FAILED=0

for sub in "${SUBMODULES[@]}"; do
  if [ ! -d "$sub/.git" ]; then
    echo -e "${YELLOW}Skip $sub (not a submodule or not initialized)${NC}"
    continue
  fi
  name=$(basename "$sub")
  echo -n "Checking $name... "

  # Uncommitted changes (excluding ignored files)
  if ! git -C "$sub" diff --quiet || ! git -C "$sub" diff --cached --quiet 2>/dev/null; then
    echo -e "${RED}has uncommitted changes${NC}"
    echo "  Commit and push in $sub first, then push this repo."
    FAILED=1
    continue
  fi

  # Unpushed commits (compare to origin/main)
  AHEAD=$(git -C "$sub" rev-list origin/main..HEAD --count 2>/dev/null || echo "0")
  if [ "${AHEAD:-0}" -gt 0 ]; then
    echo -e "${YELLOW}pushing ($AHEAD commit(s))${NC}"
    if ! git -C "$sub" push origin main; then
      echo -e "${RED}Push failed for $sub${NC}"
      FAILED=1
    else
      echo -e "${GREEN}pushed${NC}"
    fi
  else
    echo -e "${GREEN}in sync${NC}"
  fi
done

if [ $FAILED -eq 1 ]; then
  exit 1
fi

# If parent has modified submodule refs (we just pushed submodules), stage them
PARENT_REF_CHANGED=0
for sub in "${SUBMODULES[@]}"; do
  if git -C "$REPO_ROOT" diff --name-only -- "$sub" | grep -q .; then
    PARENT_REF_CHANGED=1
    break
  fi
done
if [ $PARENT_REF_CHANGED -eq 1 ]; then
  echo -e "${YELLOW}Submodule refs changed; staging for parent commit.${NC}"
  git add .claude/agents .claude/skills 2>/dev/null || true
fi
exit 0
