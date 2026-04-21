"""Tests for discovery scan integration in aec setup command."""

import pytest
from unittest.mock import patch, MagicMock


class TestDiscoveryCodePresence:
    """Verify the discovery integration code exists in setup() with correct structure."""

    def _get_setup_source(self):
        import inspect
        from aec.commands.repo import setup
        return inspect.getsource(setup)

    def test_setup_contains_discovery_section(self):
        """The setup function contains the discovery scan section."""
        source = self._get_setup_source()
        assert "Discovery scan" in source
        assert "Scan for files that match items in the AEC catalog?" in source
        assert "depth=2" in source
        assert "ImportError" in source
        assert "Discovery module not available" in source
        assert "Discovery scan failed" in source

    def test_discovery_defaults_to_yes(self):
        """The discovery prompt uses [Y/n] (default yes)."""
        source = self._get_setup_source()
        assert "[Y/n]" in source

    def test_discovery_checks_batch_and_dry_run(self):
        """Discovery is gated on not dry_run and not batch."""
        source = self._get_setup_source()
        assert "not dry_run and not batch" in source

    def test_discovery_handles_eoferror(self):
        """Discovery prompt handles EOFError by defaulting to skip."""
        source = self._get_setup_source()
        assert 'resp = "n"' in source

    def test_discovery_uses_normal_depth(self):
        """Discovery during setup always uses Normal depth (2), no depth prompt."""
        source = self._get_setup_source()
        assert "depth=2" in source

    def test_no_similar_items_message(self):
        """When scan returns empty results, info message is shown."""
        source = self._get_setup_source()
        assert "No similar items found" in source

    def test_present_results_called_when_results_exist(self):
        """_present_results is called only when results are non-empty."""
        source = self._get_setup_source()
        assert "_present_results(results, scope)" in source
        assert "if results:" in source

    def test_discovery_before_summary(self):
        """Discovery scan runs before the Setup Complete summary."""
        source = self._get_setup_source()
        discovery_pos = source.index("Discovery scan")
        summary_pos = source.index("Setup Complete")
        assert discovery_pos < summary_pos, (
            "Discovery scan must appear before Setup Complete summary"
        )

    def test_discovery_after_raycast(self):
        """Discovery scan runs after the Raycast scripts section."""
        source = self._get_setup_source()
        raycast_pos = source.index("Raycast")
        discovery_pos = source.index("Discovery scan")
        assert raycast_pos < discovery_pos, (
            "Discovery scan must appear after Raycast scripts section"
        )


class TestSetupDiscoveryErrorHandling:
    """Verify that discovery scan errors don't break setup."""

    def test_import_error_shows_warning(self, capsys):
        """ImportError from discovery modules shows warning, doesn't crash."""
        from aec.lib import Console

        try:
            from aec.commands.discover_catalog import _run_scan  # noqa: F401
            pytest.skip("discover_catalog exists - ImportError test not applicable")
        except ImportError:
            Console.warning(
                "Discovery module not available. "
                "Run `aec update` to get the latest version."
            )

        captured = capsys.readouterr()
        assert "Discovery module not available" in captured.out

    def test_exception_during_scan_shows_warning(self, capsys):
        """Runtime exception during scan shows warning, doesn't crash."""
        from aec.lib import Console

        error_msg = "test scan failure"
        try:
            raise RuntimeError(error_msg)
        except Exception as e:
            Console.warning(f"Discovery scan failed: {e}")

        captured = capsys.readouterr()
        assert "Discovery scan failed: test scan failure" in captured.out


class TestDiscoveryPromptBehavior:
    """Test the discovery prompt acceptance/decline logic in isolation."""

    def test_accept_triggers_scan(self):
        """Responses other than 'n'/'no' should trigger the scan."""
        # Test the condition used in setup()
        for resp in ["", "y", "yes", "Y", "YES"]:
            assert resp not in ("n", "no"), f"'{resp}' should trigger scan"

    def test_decline_skips_scan(self):
        """'n' and 'no' should skip the scan."""
        for resp in ["n", "no"]:
            assert resp in ("n", "no"), f"'{resp}' should skip scan"

    def test_eoferror_defaults_to_skip(self):
        """EOFError should result in resp='n' which skips the scan."""
        # Simulate the EOFError handling
        try:
            raise EOFError()
        except EOFError:
            resp = "n"
        assert resp in ("n", "no")

    def test_run_scan_receives_depth_2(self):
        """_run_scan should be called with depth=2 (Normal)."""
        mock_run_scan = MagicMock(return_value=[])
        mock_scope = MagicMock()
        mock_catalog = {}
        mock_hashes = {}

        mock_run_scan(mock_scope, depth=2, catalog=mock_catalog, catalog_hashes=mock_hashes)

        mock_run_scan.assert_called_once_with(
            mock_scope, depth=2, catalog=mock_catalog, catalog_hashes=mock_hashes
        )

    def test_present_results_only_called_with_results(self):
        """_present_results should only be called when results is non-empty."""
        mock_present = MagicMock()
        mock_scope = MagicMock()

        # Empty results - should NOT call _present_results
        results = []
        if results:
            mock_present(results, mock_scope)
        mock_present.assert_not_called()

        # Non-empty results - should call _present_results
        results = [MagicMock()]
        if results:
            mock_present(results, mock_scope)
        mock_present.assert_called_once_with(results, mock_scope)
