# -*- coding: utf-8 -*-
"""Local conftest.py plugins contain directory-specific hook implementations.

https://docs.pytest.org/en/7.1.x/how-to/writing_plugins.html#localplugin
"""

# pylint: disable=missing-function-docstring, unused-argument, import-outside-toplevel


def pytest_runtest_setup(item):
    """Called to perform the setup phase for a test item.

    https://docs.pytest.org/en/7.1.x/reference/reference.html#pytest.hookspec.pytest_runtest_setup

    The default implementation runs setup() on item and all of its parents
    (which haven’t been setup yet).
    This includes obtaining the values of fixtures required by the item
    (which haven’t been obtained yet).
    """
    import os
    if not os.path.realpath(os.curdir).endswith("/tests"):
        os.chdir("tests")
