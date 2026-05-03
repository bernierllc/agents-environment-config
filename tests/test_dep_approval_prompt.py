"""Tests for dep_approval_prompt."""
import pytest
from unittest.mock import patch


class TestPromptDepInstall:
    def _make_deps(self, names):
        return [{"name": n, "version": "1.0.0", "reason": f"Reason for {n}"} for n in names]

    def test_assume_yes_returns_true_without_prompting(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        result = prompt_dep_install("target", "1.0.0", self._make_deps(["dep-a"]), assume_yes=True)
        assert result is True

    def test_y_response_returns_true(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        with patch("builtins.input", return_value="y"):
            result = prompt_dep_install("target", "1.0.0", self._make_deps(["dep-a"]))
        assert result is True

    def test_n_response_returns_false(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        with patch("builtins.input", return_value="n"):
            result = prompt_dep_install("target", "1.0.0", self._make_deps(["dep-a"]))
        assert result is False

    def test_each_mode_all_approved_returns_true(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        # First input: "each", then "y" for each dep
        with patch("builtins.input", side_effect=["each", "y", "y"]):
            result = prompt_dep_install("target", "1.0.0", self._make_deps(["dep-a", "dep-b"]))
        assert result is True

    def test_each_mode_first_rejected_returns_false(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        with patch("builtins.input", side_effect=["each", "n"]):
            result = prompt_dep_install("target", "1.0.0", self._make_deps(["dep-a", "dep-b"]))
        assert result is False

    def test_eoferror_returns_false(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        with patch("builtins.input", side_effect=EOFError):
            result = prompt_dep_install("target", "1.0.0", self._make_deps(["dep-a"]))
        assert result is False

    def test_no_deps_returns_true_without_prompting(self):
        from aec.lib.dep_approval_prompt import prompt_dep_install
        # No input should be needed when there are no deps
        result = prompt_dep_install("target", "1.0.0", [])
        assert result is True


class TestPromptDepUpgradeConflict:
    def test_assume_yes_returns_true_without_prompting(self):
        from aec.lib.dep_approval_prompt import prompt_dep_upgrade_conflict
        result = prompt_dep_upgrade_conflict(
            "target", "3.5.0", "dep-skill", "3.4.0", "3.3.0", assume_yes=True
        )
        assert result is True

    def test_y_response_returns_true(self):
        from aec.lib.dep_approval_prompt import prompt_dep_upgrade_conflict
        with patch("builtins.input", return_value="y"):
            result = prompt_dep_upgrade_conflict(
                "target", "3.5.0", "dep-skill", "3.4.0", "3.3.0"
            )
        assert result is True

    def test_n_response_returns_false(self):
        from aec.lib.dep_approval_prompt import prompt_dep_upgrade_conflict
        with patch("builtins.input", return_value="n"):
            result = prompt_dep_upgrade_conflict(
                "target", "3.5.0", "dep-skill", "3.4.0", "3.3.0"
            )
        assert result is False

    def test_cancel_response_returns_false(self):
        from aec.lib.dep_approval_prompt import prompt_dep_upgrade_conflict
        with patch("builtins.input", return_value="cancel"):
            result = prompt_dep_upgrade_conflict(
                "target", "3.5.0", "dep-skill", "3.4.0", "3.3.0"
            )
        assert result is False

    def test_eoferror_returns_false(self):
        from aec.lib.dep_approval_prompt import prompt_dep_upgrade_conflict
        with patch("builtins.input", side_effect=EOFError):
            result = prompt_dep_upgrade_conflict(
                "target", "3.5.0", "dep-skill", "3.4.0", "3.3.0"
            )
        assert result is False

    def test_prompt_includes_version_context(self, capsys):
        from aec.lib.dep_approval_prompt import prompt_dep_upgrade_conflict
        prompt_text = []
        def capture_input(msg):
            prompt_text.append(msg)
            return "n"
        with patch("builtins.input", side_effect=capture_input):
            prompt_dep_upgrade_conflict(
                "playwright-test-generator", "3.5.0", "verification-writer", "3.4.0", "3.3.0"
            )
        assert len(prompt_text) == 1
        assert "3.5.0" in prompt_text[0]
        assert "verification-writer" in prompt_text[0]
        assert "3.4.0" in prompt_text[0]
        assert "3.3.0" in prompt_text[0]
