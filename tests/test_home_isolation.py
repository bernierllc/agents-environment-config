"""Guard: the suite never touches the developer's real home directory."""

import os
from pathlib import Path

from tests import conftest


def test_home_is_a_throwaway_dir():
    assert os.environ["HOME"] == conftest._TEST_HOME
    assert Path.home() == Path(conftest._TEST_HOME)


def test_aec_state_paths_live_under_the_test_home():
    """Fails if aec was imported before conftest redirected HOME."""
    from aec.lib import config

    for path in (config.AEC_HOME, config.INSTALLED_SKILLS, config.INSTALLED_MANIFEST_V2,
                 config.AEC_PREFERENCES):
        assert Path(conftest._TEST_HOME) in Path(path).parents, path
    if conftest._REAL_HOME:
        assert not str(config.AEC_HOME).startswith(conftest._REAL_HOME + os.sep + ".")
