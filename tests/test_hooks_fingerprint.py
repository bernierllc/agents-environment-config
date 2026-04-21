"""Tests for aec.lib.hooks.fingerprint — stable content hashing."""


class TestFingerprintHook:
    def test_sha256_prefix(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        assert fingerprint_hook({}).startswith("sha256:")

    def test_same_content_same_fingerprint(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        a = {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "c"}]}
        b = {"hooks": [{"command": "c", "type": "command"}], "matcher": "Edit|Write"}
        assert fingerprint_hook(a) == fingerprint_hook(b)

    def test_different_content_different_fingerprint(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        assert fingerprint_hook({"a": 1}) != fingerprint_hook({"a": 2})

    def test_deterministic_across_calls(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        p = {"nested": {"b": 2, "a": 1}, "list": [3, 1, 2]}
        assert fingerprint_hook(p) == fingerprint_hook(p)

    def test_unicode_preserved(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        assert fingerprint_hook({"x": "café"}) == fingerprint_hook({"x": "café"})

    def test_hex_digest_length(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        fp = fingerprint_hook({"x": 1})
        # "sha256:" + 64 hex chars
        assert len(fp) == 7 + 64
