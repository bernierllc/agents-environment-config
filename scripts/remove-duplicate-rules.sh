#!/bin/bash
# Files to remove - covered by global rules
# Generated with safety checks

# Note: set -e and set -u disabled to allow flexibility

# Check for dry-run flag
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]] || [[ "${1:-}" == "-n" ]]; then
  DRY_RUN=true
  echo "DRY RUN MODE - No files will be removed"
  echo "========================================"
fi

if [ "$DRY_RUN" = false ]; then
  echo "Removing project-specific rule files covered by global rules..."
else
  echo "Dry run: Would remove project-specific rule files covered by global rules..."
fi
echo "Safety checks enabled - only removing files in .cursor/rules directories"

removed_count=0
skipped_count=0

# Removing: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/plans.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/environment.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibe_scaffold/.cursor/rules/development.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/database.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/auth.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc
if [ -f "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc" ] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc"
  else
    rm "/Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/Builders_Main/vibeapp.studio/.cursor/rules/versioning/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/production-ready.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/plans.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-driven-config.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/error-handling.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/deployment.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/logging.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/ui.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/bernierllc-packages.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/el_new_app/.cursor/rules/accessibility.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/api-client-ui.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/strict-typing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/production-ready.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/plans.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/testing-patterns.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/error-handling.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/logging.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/ui.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/quality-gates.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc
if [ -f "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc" ] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc"
  else
    rm "/Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/EarnLearn/fork/.cursor/rules/accessibility.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/react-native.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/supabase.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/typescript-typing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-debugging.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/tamagui-properties.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/api-testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/ui-development.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc
if [ -f "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc" ] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc"
  else
    rm "/Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/SCF-Neue/.cursor/rules/code-quality.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc
if [ -f "/Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc" ] && [[ "/Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc"
  else
    rm "/Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/complement_cursor/.cursor/rules/cursor-rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc
if [ -f "/Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc" ] && [[ "/Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc"
  else
    rm "/Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/complement_cursor/.cursor/rules/github-rule.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc
if [ -f "/Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc" ] && [[ "/Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc"
  else
    rm "/Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/formExpert.co/.cursor/rules/plans.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc
if [ -f "/Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc" ] && [[ "/Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc"
  else
    rm "/Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/formExpert.co/.cursor/rules/workflow.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc
if [ -f "/Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc" ] && [[ "/Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc"
  else
    rm "/Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/formExpert.co/.cursor/rules/authentication-boundaries.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/houseofgenius/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc
if [ -f "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc" ] && [[ "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc"
  else
    rm "/Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/houseofgenius/.cursor/rules/testing-changes.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/01-python-style.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/suggest_missing_rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/observability.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/security_secrets.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/02-fastapi.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc
if [ -f "/Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc" ] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc"
  else
    rm "/Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/Sites/.cursor/rules/rbac_okta.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc
if [ -f "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc" ] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc"
  else
    rm "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/energy_site/.cursor/rules/plans.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/energy_site/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc
if [ -f "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc" ] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc"
  else
    rm "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/energy_site/.cursor/rules/pull-requests.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/energy_site/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc
if [ -f "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc" ] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc"
  else
    rm "/Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mara/energy_site/.cursor/rules/branching.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/plans-checklists.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/bernierllc-packages.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/documentation.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc
if [ -f "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc" ] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc"
  else
    rm "/Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc
if [ -f "/Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc" ] && [[ "/Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc"
  else
    rm "/Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/mcp-ask-questions/.cursor/rules/commits.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc
if [ -f "/Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc" ] && [[ "/Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc"
  else
    rm "/Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/neveradmin/.cursor/rules/cursor-execution-rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc
if [ -f "/Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc" ] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc"
  else
    rm "/Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/neverhub/.cursor/rules/cursor-rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc
if [ -f "/Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc" ] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc"
  else
    rm "/Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/neverhub/.cursor/rules/build-quality.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/neverhub/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc
if [ -f "/Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc" ] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc"
  else
    rm "/Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/neverhub/.cursor/rules/questions-documentation.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc
if [ -f "/Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc" ] && [[ "/Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc"
  else
    rm "/Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/ports/test-project/.cursor/rules/project-setup-cli.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc
if [ -f "/Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc" ] && [[ "/Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc"
  else
    rm "/Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/ports/test-project/.cursor/rules/port-management.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/api-verification-scripts.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/flake8-formatting.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/linter-errors.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/react-hydration-errors.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/dev-environment.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/python-server-apis.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/api-request-flow.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/documentation.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/api-standards.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc
if [ -f "/Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc" ] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc"
  else
    rm "/Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/prevost/.cursor/rules/app-architecture.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-workflow.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/documentation.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/server.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/git-cursor-rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/typescript-strict.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/code-quality.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/alembic.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/accessibility-admin.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/questions-documentation.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc
if [ -f "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc" ] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc"
  else
    rm "/Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/robert_champion/barevents/.cursor/rules/api-integration.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/cursor-rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/git-workflow.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/publishing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/package-reuse.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/plans-and-checklists.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/package-management.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/rules.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/rules.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/rules.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/documentation/readme.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/markdown/markdown-rules.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/scripts/npm-publish.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/coding/linting-type-safety.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc
if [ -f "/Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc" ] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc"
  else
    rm "/Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/tools/.cursor/rules/coding/testing-standards.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/database.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/git.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/testing.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/typescript.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/styling.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/api-standards.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/nextjs-react.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/bernierllc-packages.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/troubleshooting/errors.mdc"
  ((skipped_count++))
fi

# Removing: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc
if [ -f "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc" ] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc" == *".cursor/rules"* ]] && [[ "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc" != *"agents-environment-config"* ]]; then
  if [ "$DRY_RUN" = true ]; then
    echo "✓ Would remove: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc"
  else
    rm "/Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc"
    echo "✓ Removed: /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc"
  fi
  ((removed_count++))
else
  echo "✗ Skipped (safety check failed): /Users/mattbernier/projects/vibeapp.studio/.cursor/rules/versioning/git.mdc"
  ((skipped_count++))
fi

echo ""
if [ "$DRY_RUN" = true ]; then
  echo "Dry run complete!"
  echo "Would remove: $removed_count files"
else
  echo "Done!"
  echo "Removed: $removed_count files"
fi
echo "Skipped: $skipped_count files"