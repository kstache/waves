import os
import sys
import pathlib
import subprocess

import pytest


env = os.environ.copy()
try:
    import waves
except ModuleNotFoundError:
    # TODO: resolve from package? SConstruct?
    package_parent_path = str(pathlib.Path(".").resolve().parent)
    key = "PYTHONPATH"
    if key in env:
        env[key] = f"{package_parent_path}:{env[key]}"
    else:
        env[key] = package_parent_path

@pytest.mark.systemtest
@pytest.mark.parametrize("command", [
    ["scons", ".", "--sconstruct=scons_quickstart_SConstruct", "--keep-going"],
    ["scons", ".", "--sconstruct=scons_multiactiontask_SConstruct", "--keep-going"],
    ["scons", ".", "--sconstruct=waves_quickstart_SConstruct", "--keep-going"],
    ["scons", ".", "--sconstruct=tutorial_00_SConstruct", "--keep-going", "--unconditional-build"],
])
def test_run_tutorial(command):
    result = subprocess.check_output(command, env=env).decode('utf-8')
