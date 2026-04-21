"""Tests for aec.lib.hooks.predicates — spec §1.4 when-predicates."""

from aec.lib.hooks.schema import WhenPredicate


class TestEvaluateWhen:
    def test_empty_predicate_applies(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate()
        result = evaluate_when(pred, tmp_path)
        assert result.applied is True

    def test_none_predicate_applies(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        result = evaluate_when(None, tmp_path)
        assert result.applied is True

    def test_repo_has_match(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "pyproject.toml").write_text("")
        pred = WhenPredicate(repo_has=["pyproject.toml"])
        assert evaluate_when(pred, tmp_path).applied is True

    def test_repo_has_missing_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(repo_has=["pyproject.toml"])
        result = evaluate_when(pred, tmp_path)
        assert result.applied is False
        assert "pyproject.toml" in result.reason

    def test_repo_has_any_matches_one(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "package.json").write_text("")
        pred = WhenPredicate(repo_has_any=["tsconfig.json", "package.json"])
        assert evaluate_when(pred, tmp_path).applied is True

    def test_repo_has_any_all_missing_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(repo_has_any=["a.txt", "b.txt"])
        assert evaluate_when(pred, tmp_path).applied is False

    def test_repo_lacks_passes_when_absent(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(repo_lacks=["forbidden.txt"])
        assert evaluate_when(pred, tmp_path).applied is True

    def test_repo_lacks_skips_when_present(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "forbidden.txt").write_text("")
        pred = WhenPredicate(repo_lacks=["forbidden.txt"])
        assert evaluate_when(pred, tmp_path).applied is False

    def test_custom_check_true_applies(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(custom_check="true")
        assert evaluate_when(pred, tmp_path).applied is True

    def test_custom_check_false_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(custom_check="false")
        result = evaluate_when(pred, tmp_path)
        assert result.applied is False

    def test_custom_check_timeout_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(custom_check="sleep 10")
        result = evaluate_when(pred, tmp_path, timeout_s=1)
        assert result.applied is False
        assert "timeout" in result.reason.lower()

    def test_combined_all_must_apply(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "pyproject.toml").write_text("")
        pred = WhenPredicate(
            repo_has=["pyproject.toml"], repo_lacks=["forbidden.txt"]
        )
        assert evaluate_when(pred, tmp_path).applied is True
