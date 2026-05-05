from pathlib import Path

from aec.lib.org_config.hashing import hash_config_bytes, hash_config_file


def test_hash_config_bytes_is_sha256_hex():
    h = hash_config_bytes(b"hello world")
    assert h == "sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_hash_config_file_matches_bytes(tmp_path: Path):
    p = tmp_path / "x.yaml"
    p.write_bytes(b"hello world")
    assert hash_config_file(p) == hash_config_bytes(b"hello world")


def test_hash_includes_prefix():
    h = hash_config_bytes(b"x")
    assert h.startswith("sha256:")
