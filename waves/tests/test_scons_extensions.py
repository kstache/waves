"""Test WAVES SCons builders and support functions"""

import os
import pathlib
from contextlib import nullcontext as does_not_raise
import unittest
from unittest.mock import patch, call
import subprocess

import pytest
import SCons.Node.FS

from waves import scons_extensions
from waves._settings import _cd_action_prefix
from waves._settings import _abaqus_environment_extension
from waves._settings import _abaqus_datacheck_extensions
from waves._settings import _abaqus_explicit_extensions
from waves._settings import _abaqus_standard_extensions
from waves._settings import _abaqus_solver_common_suffixes
from waves._settings import _stdout_extension
from common import platform_check


fs = SCons.Node.FS.FS()

testing_windows, root_fs = platform_check()


def check_action_string(nodes, post_action, node_count, action_count, expected_string):
    """Verify the expected action string against a builder's target nodes

    :param SCons.Node.NodeList nodes: Target node list returned by a builder
    :param list post_action: list of post action strings passed to builder
    :param int node_count: expected length of ``nodes``
    :param int action_count: expected length of action list for each node
    :param str expected_string: the builder's action string.

    .. note::

       The method of interrogating a node's action list results in a newline separated string instead of a list of
       actions. The ``expected_string`` should contain all elements of the expected action list as a single, newline
       separated string. The ``action_count`` should be set to ``1`` until this method is updated to search for the
       finalized action list.
    """
    for action in post_action:
        expected_string = expected_string + f"\ncd ${{TARGET.dir.abspath}} && {action}"
    assert len(nodes) == node_count
    for node in nodes:
        node.get_executor()
        assert len(node.executor.action_list) == action_count
        assert str(node.executor.action_list[0]) == expected_string


def check_expected_targets(nodes, solver, stem, suffixes):
    """Verify the expected action string against a builder's target nodes

    :param SCons.Node.NodeList nodes: Target node list returned by a builder
    :param str solver: emit file extensions based on the value of this variable (standard/explicit/datacheck).
    :param str stem: stem name of file
    :param list suffixes: list of override suffixes provided to the task
    """
    expected_suffixes = [_stdout_extension, _abaqus_environment_extension]
    if suffixes:
        expected_suffixes.extend(suffixes)
    elif solver == 'standard':
        expected_suffixes.extend(_abaqus_standard_extensions)
    elif solver == 'explicit':
        expected_suffixes.extend(_abaqus_explicit_extensions)
    elif solver == 'datacheck':
        expected_suffixes.extend(_abaqus_datacheck_extensions)
    else:
        expected_suffixes.extend(_abaqus_solver_common_suffixes)
    suffixes = [str(node).split(stem)[-1] for node in nodes]
    assert set(expected_suffixes) == set(suffixes)


# TODO: Remove the **kwargs check and warning for v1.0.0 release
# https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
def test_warn_kwarg_change():
    with patch("warnings.warn") as mock_warn:
        program = scons_extensions._warn_kwarg_change({'old_kwarg': True}, "old_kwarg", new_kwarg="new_kwarg")
        mock_warn.assert_called_once()
        assert program == True
    with patch("warnings.warn") as mock_warn:
        program = scons_extensions._warn_kwarg_change({'old_kwarg': False}, "old_kwarg", new_kwarg="new_kwarg")
        mock_warn.assert_called_once()
        assert program == False
    with patch("warnings.warn") as mock_warn:
        program = scons_extensions._warn_kwarg_change({}, "old_kwarg", new_kwarg="new_kwarg")
        mock_warn.assert_not_called()
        assert program == None


prepend_env_input = {
    "path exists": (f"{root_fs}program", True, does_not_raise()),
    "path does not exist": (f"{root_fs}notapath", False, pytest.raises(FileNotFoundError))
}


@pytest.mark.unittest
@pytest.mark.parametrize("program, mock_exists, outcome",
                         prepend_env_input.values(),
                         ids=prepend_env_input.keys())
def test_append_env_path(program, mock_exists, outcome):
    env = SCons.Environment.Environment()
    with patch("pathlib.Path.exists", return_value=mock_exists), outcome:
        try:
            scons_extensions.append_env_path(program, env)
            assert root_fs == env["ENV"]["PATH"].split(os.pathsep)[-1]
            assert "PYTHONPATH" not in env["ENV"]
            assert "LD_LIBRARY_PATH" not in env["ENV"]
        finally:
            pass


substitution_dictionary = {"thing1": 1, "thing_two": "two"}
substitution_syntax_input = {
    "default characters": (substitution_dictionary, {}, {"@thing1@": 1, "@thing_two@": "two"}),
    "provided pre/postfix": (substitution_dictionary, {"prefix": "$", "postfix": "%"},
                             {"$thing1%": 1, "$thing_two%": "two"}),
    "int key": ({1: "one"}, {}, {"@1@": "one"}),
    "float key": ({1.0: "one"}, {}, {"@1.0@": "one"}),
    "nested": ({"nest_parent": {"nest_child": 1}, "thing_two": "two"}, {},
               {"@nest_parent@": {"nest_child": 1}, "@thing_two@": "two"})
}


@pytest.mark.unittest
@pytest.mark.parametrize("substitution_dictionary, keyword_arguments, expected_dictionary",
                         substitution_syntax_input.values(),
                         ids=substitution_syntax_input.keys())
def test_substitution_syntax(substitution_dictionary, keyword_arguments, expected_dictionary):
    output_dictionary = scons_extensions.substitution_syntax(substitution_dictionary, **keyword_arguments)
    assert output_dictionary == expected_dictionary


quote_spaces_in_path_input = {
    "string, no spaces": (
        "/path/without_space/executable",
        pathlib.Path("/path/without_space/executable")
    ),
    "string, spaces": (
        "/path/with space/executable",
        pathlib.Path("/path/\"with space\"/executable")
    ),
    "pathlib, no spaces": (
        pathlib.Path("/path/without_space/executable"),
        pathlib.Path("/path/without_space/executable")
    ),
    "pathlib, spaces": (
        pathlib.Path("/path/with space/executable"),
        pathlib.Path("/path/\"with space\"/executable")
    ),
    "space in root": (
        pathlib.Path("/path space/with space/executable"),
        pathlib.Path("/\"path space\"/\"with space\"/executable")
    ),
    "relative path": (
        pathlib.Path("path space/without_space/executable"),
        pathlib.Path("\"path space\"/without_space/executable")
    ),
    "space in executable": (
        pathlib.Path("path/without_space/executable space"),
        pathlib.Path("path/without_space/\"executable space\"")
    )
}


@pytest.mark.unittest
@pytest.mark.parametrize("path, expected",
                         quote_spaces_in_path_input.values(),
                         ids=quote_spaces_in_path_input.keys())
def test_quote_spaces_in_path(path, expected):
    assert scons_extensions._quote_spaces_in_path(path) == expected


return_environment = {
    "no newlines": (b"thing1=a\x00thing2=b", {"thing1": "a", "thing2": "b"}),
    "newlines": (b"thing1=a\nnewline\x00thing2=b", {"thing1": "a\nnewline", "thing2": "b"})
}


@pytest.mark.unittest
@pytest.mark.parametrize("stdout, expected",
                         return_environment.values(),
                         ids=return_environment.keys())
def test_return_environment(stdout, expected):
    """
    :param bytes stdout: byte string with null delimited shell environment variables
    :param dict expected: expected dictionary output containing string key:value pairs and preserving newlines
    """
    mock_run_return = subprocess.CompletedProcess(args="dummy", returncode=0, stdout=stdout)
    with patch("subprocess.run", return_value=mock_run_return):
        environment_dictionary = scons_extensions._return_environment("dummy")
    assert environment_dictionary == expected


cache_environment = {
        # cache,       overwrite_cache, expected,        file_exists
    "no cache":
        (None,         False,           {"thing1": "a"}, False),
    "cache exists":
        ("dummy.yaml", False,           {"thing1": "a"}, True),
    "cache doesn't exist":
        ("dummy.yaml", False,           {"thing1": "a"}, False),
    "overwrite cache":
        ("dummy.yaml", True,            {"thing1": "a"}, True),
    "don't overwrite cache":
        ("dummy.yaml", False,           {"thing1": "a"}, False)
}


@pytest.mark.unittest
@pytest.mark.parametrize("cache, overwrite_cache, expected, file_exists",
                         cache_environment.values(),
                         ids=cache_environment.keys())
def test_cache_environment(cache, overwrite_cache, expected, file_exists):
    with patch("waves.scons_extensions._return_environment", return_value=expected) as return_environment, \
         patch("yaml.safe_load", return_value=expected) as yaml_load, \
         patch("pathlib.Path.exists", return_value=file_exists), \
         patch("yaml.safe_dump") as yaml_dump, \
         patch("builtins.open"):
        environment_dictionary = scons_extensions._cache_environment("dummy command", cache=cache,
                                                                     overwrite_cache=overwrite_cache)
        if cache and file_exists and not overwrite_cache:
            yaml_load.assert_called_once()
            return_environment.assert_not_called()
        else:
            yaml_load.assert_not_called()
            return_environment.assert_called_once()
        if cache:
            yaml_dump.assert_called_once()
    assert environment_dictionary == expected


shell_environment = {
    "no cache": (None, False, {"thing1": "a"}),
    "cache": ("dummy.yaml", False, {"thing1": "a"}),
    "cache overwrite": ("dummy.yaml", True, {"thing1": "a"}),
}


@pytest.mark.unittest
@pytest.mark.parametrize("cache, overwrite_cache, expected",
                         shell_environment.values(),
                         ids=shell_environment.keys())
def test_shell_environment(cache, overwrite_cache, expected):
    with patch("waves.scons_extensions._cache_environment", return_value=expected) as cache_environment:
        env = scons_extensions.shell_environment("dummy")
        assert cache_environment.called_once_with("dummy", cache=cache, overwrite_cache=overwrite_cache)
    # Check that the expected dictionary is a subset of the SCons construction environment
    assert all(env["ENV"].get(key, None) == value for key, value in expected.items())

prepended_string = f"{_cd_action_prefix} "
post_action_list = {
    "list1": (["thing1"], [prepended_string + "thing1"]),
    "list2": (["thing1", "thing2"], [prepended_string + "thing1", prepended_string + "thing2"]),
    "tuple": (("thing1",), [prepended_string + "thing1"]),
    "str":  ("thing1", [prepended_string + "thing1"]),
}


@pytest.mark.unittest
@pytest.mark.parametrize("post_action, expected",
                         post_action_list.values(),
                         ids=post_action_list.keys())
def test_construct_post_action_list(post_action, expected):
    output = scons_extensions._construct_post_action_list(post_action)
    assert output == expected


source_file = fs.File("dummy.py")
journal_emitter_input = {
    "one target": (["target.cae"],
                   [source_file],
                   ["target.cae", "target.stdout", "target.abaqus_v6.env"]),
    "subdirectory": (["set1/dummy.cae"],
                    [source_file],
                    ["set1/dummy.cae", f"set1{os.sep}dummy.stdout", f"set1{os.sep}dummy.abaqus_v6.env"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, source, expected",
                         journal_emitter_input.values(),
                         ids=journal_emitter_input.keys())
def test_abaqus_journal_emitter(target, source, expected):
    target, source = scons_extensions._abaqus_journal_emitter(target, source, None)
    assert target == expected


# TODO: Figure out how to cleanly reset the construction environment between parameter sets instead of passing a new
# target per set.
abaqus_journal_input = {
    "default behavior": ("abaqus", [], 3, 1, ["journal1.cae"]),
    "different command": ("dummy", [], 3, 1, ["journal2.cae"]),
    "post action": ("abaqus", ["post action"], 3, 1, ["journal3.cae"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("program, post_action, node_count, action_count, target_list",
                         abaqus_journal_input.values(),
                         ids=abaqus_journal_input.keys())
def test_abaqus_journal(program, post_action, node_count, action_count, target_list):
    env = SCons.Environment.Environment()
    expected_string = f'cd ${{TARGET.dir.abspath}} && {program} -information environment > ' \
                       '${TARGET.filebase}.abaqus_v6.env\n' \
                      f'cd ${{TARGET.dir.abspath}} && {program} cae -noGui ${{SOURCE.abspath}} ' \
                       '${abaqus_options} -- ${journal_options} > ${TARGET.filebase}.stdout 2>&1'

    env.Append(BUILDERS={"AbaqusJournal": scons_extensions.abaqus_journal(program, post_action)})
    nodes = env.AbaqusJournal(target=target_list, source=["journal.py"], journal_options="")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)

    # TODO: Remove the **kwargs and <name>_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    env.Append(BUILDERS={"AbaqusJournalDeprecatedKwarg": scons_extensions.abaqus_journal(abaqus_program=program, post_action=post_action)})
    nodes = env.AbaqusJournalDeprecatedKwarg(target=target_list, source=["journal.py"], journal_options="")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)


def test_sbatch_abaqus_journal():
    expected = 'sbatch --wait --wrap "cd ${TARGET.dir.abspath} && abaqus -information environment > ' \
        '${TARGET.filebase}.abaqus_v6.env && cd ${TARGET.dir.abspath} && abaqus cae -noGui ${SOURCE.abspath} ' \
        '${abaqus_options} -- ${journal_options} > ${TARGET.filebase}.stdout 2>&1"'
    builder = scons_extensions.sbatch_abaqus_journal()
    assert builder.action.cmd_list == expected


source_file = fs.File("root.inp")
solver_emitter_input = {
    "empty targets": (
        "job",
        None,
        [],
        [source_file],
        ["job.stdout", "job.abaqus_v6.env", "job.odb", "job.dat", "job.msg", "job.com", "job.prt"],
        does_not_raise()
    ),
    "empty targets, suffixes override": (
        "job",
        [".odb"],
        [],
        [source_file],
        ["job.stdout", "job.abaqus_v6.env", "job.odb"],
        does_not_raise()
    ),
    "empty targets, suffixes override empty list": (
        "job",
        [],
        [],
        [source_file],
        ["job.stdout", "job.abaqus_v6.env"],
        does_not_raise()
    ),
    "one targets": (
        "job",
        None,
        ["job.sta"],
        [source_file],
        ["job.sta", "job.stdout", "job.abaqus_v6.env", "job.odb", "job.dat", "job.msg", "job.com", "job.prt"],
        does_not_raise()
    ),
    "one targets, override suffixes": (
        "job",
        [".odb"],
        ["job.sta"],
        [source_file],
        ["job.sta", "job.stdout", "job.abaqus_v6.env", "job.odb"],
        does_not_raise()
    ),
    "one targets, override suffixes string": (
        "job",
        ".odb",
        ["job.sta"],
        [source_file],
        ["job.sta", "job.stdout", "job.abaqus_v6.env", "job.odb"],
        does_not_raise()
    ),
    "subdirectory": (
        "job",
        None,
        ["set1/job.sta"],
        [source_file],
        ["set1/job.sta", f"set1{os.sep}job.stdout", f"set1{os.sep}job.abaqus_v6.env", f"set1{os.sep}job.odb", f"set1{os.sep}job.dat",
         f"set1{os.sep}job.msg", f"set1{os.sep}job.com", f"set1{os.sep}job.prt"],
        does_not_raise()
    ),
    "subdirectory, override suffixes": (
        "job",
        [".odb"],
        ["set1/job.sta"],
        [source_file],
        ["set1/job.sta", f"set1{os.sep}job.stdout", f"set1{os.sep}job.abaqus_v6.env", f"set1{os.sep}job.odb"],
        does_not_raise()
    ),
    "missing job_name": (
        None,
        None,
        [],
        [source_file],
        ["root.stdout", "root.abaqus_v6.env", "root.odb", "root.dat", "root.msg", "root.com", "root.prt"],
        does_not_raise()
    ),
    "missing job_name, override suffixes": (
        None,
        [".odb"],
        [],
        [source_file],
        ["root.stdout", "root.abaqus_v6.env", "root.odb"],
        does_not_raise()
    )
}


@pytest.mark.unittest
@pytest.mark.parametrize("job_name, suffixes, target, source, expected, outcome",
                         solver_emitter_input.values(),
                         ids=solver_emitter_input.keys())
def test_abaqus_solver_emitter(job_name, suffixes, target, source, expected, outcome):
    env = SCons.Environment.Environment()
    env["job_name"] = job_name
    env["suffixes"] = suffixes
    with outcome:
        try:
            scons_extensions._abaqus_solver_emitter(target, source, env)
        finally:
            assert target == expected


# TODO: Figure out how to cleanly reset the construction environment between parameter sets instead of passing a new
# target per set.
abaqus_solver_input = {
    "default behavior": ("abaqus", [], 7, 1, ["input1.inp"], None, None),
    "different command": ("dummy", [], 7, 1, ["input2.inp"], None, None),
    "post action": ("abaqus", ["post action"], 7, 1, ["input3.inp"], None, None),
    "standard solver": ("abaqus", [], 8, 1, ["input4.inp"], "standard", None),
    "explicit solver": ("abaqus", [], 8, 1, ["input5.inp"], "explicit", None),
    "datacheck solver": ("abaqus", [], 11, 1, ["input6.inp"], "datacheck", None),
    "standard solver, suffixes override": ("abaqus", [], 3, 1, ["input4.inp"], "standard", [".odb"]),
}


@pytest.mark.unittest
@pytest.mark.parametrize("program, post_action, node_count, action_count, source_list, emitter, suffixes",
                         abaqus_solver_input.values(),
                         ids=abaqus_solver_input.keys())
def test_abaqus_solver(program, post_action, node_count, action_count, source_list, emitter, suffixes):
    env = SCons.Environment.Environment()
    expected_string = f'cd ${{TARGET.dir.abspath}} && {program} -information environment > ' \
                       '${job_name}.abaqus_v6.env\n' \
                      f'cd ${{TARGET.dir.abspath}} && {program} -job ${{job_name}} -input ' \
                       '${SOURCE.filebase} ${abaqus_options} -interactive -ask_delete no ' \
                       '> ${job_name}.stdout 2>&1'

    env.Append(BUILDERS={"AbaqusSolver": scons_extensions.abaqus_solver(program, post_action, emitter)})
    nodes = env.AbaqusSolver(target=[], source=source_list, abaqus_options="", suffixes=suffixes)
    check_action_string(nodes, post_action, node_count, action_count, expected_string)
    check_expected_targets(nodes, emitter, pathlib.Path(source_list[0]).stem, suffixes)

    # TODO: Remove the **kwargs and <name>_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    env.Append(BUILDERS={"AbaqusSolverDeprecatedKwarg": scons_extensions.abaqus_solver(abaqus_program=program, post_action=post_action, emitter=emitter)})
    nodes = env.AbaqusSolverDeprecatedKwarg(target=[], source=source_list, abaqus_options="", suffixes=suffixes)
    check_action_string(nodes, post_action, node_count, action_count, expected_string)
    check_expected_targets(nodes, emitter, pathlib.Path(source_list[0]).stem, suffixes)


def test_sbatch_abaqus_solver():
    expected = 'sbatch --wait --wrap "cd ${TARGET.dir.abspath} && abaqus -information environment > ' \
               '${job_name}.abaqus_v6.env && cd ${TARGET.dir.abspath} && abaqus -job ${job_name} -input ' \
               '${SOURCE.filebase} ${abaqus_options} -interactive -ask_delete no > ${job_name}.stdout 2>&1"'
    builder = scons_extensions.sbatch_abaqus_solver()
    assert builder.action.cmd_list == expected


copy_substitute_input = {
    "strings": (["dummy", "dummy2.in", "root.inp.in", "conf.py.in"],
                ["dummy", "dummy2.in", "dummy2", "root.inp.in", "root.inp", "conf.py.in", "conf.py"]),
    "pathlib.Path()s": ([pathlib.Path("dummy"), pathlib.Path("dummy2.in")],
                        ["dummy", "dummy2.in", "dummy2"]),
}


source_file = fs.File("dummy.i")
sierra_emitter_input = {
    "one target": (["target.sierra"],
                   [source_file],
                   ["target.sierra", "target.stdout", "target.env"]),
    "subdirectory": (["set1/dummy.sierra"],
                    [source_file],
                    ["set1/dummy.sierra", f"set1{os.sep}dummy.stdout", f"set1{os.sep}dummy.env"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, source, expected",
                         sierra_emitter_input.values(),
                         ids=sierra_emitter_input.keys())
def test_sierra_emitter(target, source, expected):
    target, source = scons_extensions._sierra_emitter(target, source, None)
    assert target == expected


# TODO: Figure out how to cleanly reset the construction environment between parameter sets instead of passing a new
# target per set.
sierra_input = {
    "default behavior": ("sierra", "adagio", [], 3, 1, ["input1.i"], ['inptu1.g']),
    "different command": ("dummy", "application", [], 3, 1, ["input2.i"], ['inptu2.g']),
    "post action": ("sierra", "adagio", ["post action"], 3, 1, ["input3.i"], ['inptu3.g']),
}


@pytest.mark.unittest
@pytest.mark.parametrize("program, application, post_action, node_count, action_count, source_list, target_list",
                         sierra_input.values(),
                         ids=sierra_input.keys())
def test_sierra(program, application, post_action, node_count, action_count, source_list, target_list):
    env = SCons.Environment.Environment()
    expected_string = f'cd ${{TARGET.dir.abspath}} && {program} {application} --version > ' \
                       '${TARGET.filebase}.env\n' \
                      f'cd ${{TARGET.dir.abspath}} && {program} ${{sierra_options}} {application} ${{application_options}} -i ' \
                       '${SOURCE.file} > ${TARGET.filebase}.stdout 2>&1'

    env.Append(BUILDERS={"Sierra": scons_extensions.sierra(program, application, post_action)})
    nodes = env.Sierra(target=target_list, source=source_list, sierra_options="", application_options="")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)


def test_sbatch_sierra():
    expected = 'sbatch --wait --wrap "cd ${TARGET.dir.abspath} && sierra adagio --version > ${TARGET.filebase}.env ' \
        '&& cd ${TARGET.dir.abspath} && sierra ${sierra_options} adagio ${application_options} -i ${SOURCE.file} > ' \
        '${TARGET.filebase}.stdout 2>&1"'
    builder = scons_extensions.sbatch_sierra()
    assert builder.action.cmd_list == expected


@pytest.mark.unittest
@pytest.mark.parametrize("source_list, expected_list",
                         copy_substitute_input.values(),
                         ids=copy_substitute_input.keys())
def test_copy_substitute(source_list, expected_list):
    target_list = scons_extensions.copy_substitute(source_list, {})
    target_files = [str(target) for target in target_list]
    assert target_files == expected_list


build_subdirectory_input = {
    "no target": ([], pathlib.Path(".")),
    "no parent": (["target.ext"], pathlib.Path(".")),
    "one parent": (["set1/target.ext"], pathlib.Path("set1"))
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, expected",
                         build_subdirectory_input.values(),
                         ids=build_subdirectory_input.keys())
def test_build_subdirectory(target, expected):
    assert scons_extensions._build_subdirectory(target) == expected


source_file = fs.File("dummy.py")
first_target_emitter_input = {
    "one target": (["target.cub"],
                   [source_file],
                   ["target.cub", "target.stdout"]),
    "subdirectory": (["set1/dummy.cub"],
                    [source_file],
                    ["set1/dummy.cub", f"set1{os.sep}dummy.stdout"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, source, expected",
                         first_target_emitter_input.values(),
                         ids=first_target_emitter_input.keys())
def test_first_target_emitter(target, source, expected):
    target, source = scons_extensions._first_target_emitter(target, source, None)
    assert target == expected


# TODO: Figure out how to cleanly reset the construction environment between parameter sets instead of passing a new
# target per set.
python_script_input = {
    "default behavior": ([], 2, 1, ["python_script1.out"]),
    "different command": ([], 2, 1, ["python_script2.out"]),
    "post action": (["post action"], 2, 1, ["python_script3.out"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("post_action, node_count, action_count, target_list",
                         python_script_input.values(),
                         ids=python_script_input.keys())
def test_python_script(post_action, node_count, action_count, target_list):
    env = SCons.Environment.Environment()
    env.Append(BUILDERS={"PythonScript": scons_extensions.python_script(post_action)})
    nodes = env.PythonScript(target=target_list, source=["python_script.py"], script_options="")
    expected_string = 'cd ${TARGET.dir.abspath} && python ${python_options} ${SOURCE.abspath} ${script_options} ' \
                      '> ${TARGET.filebase}.stdout 2>&1'
    check_action_string(nodes, post_action, node_count, action_count, expected_string)


source_file = fs.File("dummy.m")
matlab_emitter_input = {
    "one target": (["target.matlab"],
                   [source_file],
                   ["target.matlab", "target.stdout", "target.matlab.env"]),
    "subdirectory": (["set1/dummy.matlab"],
                    [source_file],
                    ["set1/dummy.matlab", f"set1{os.sep}dummy.stdout", f"set1{os.sep}dummy.matlab.env"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, source, expected",
                         matlab_emitter_input.values(),
                         ids=matlab_emitter_input.keys())
def test_matlab_script_emitter(target, source, expected):
    target, source = scons_extensions._matlab_script_emitter(target, source, None)
    assert target == expected


# TODO: Figure out how to cleanly reset the construction environment between parameter sets instead of passing a new
# target per set.
matlab_script_input = {
    "default behavior": ("matlab", [], 3, 1, ["matlab_script1.out"]),
    "different command": ("/different/matlab", [], 3, 1, ["matlab_script2.out"]),
    "post action": ("matlab", ["post action"], 3, 1, ["matlab_script3.out"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("program, post_action, node_count, action_count, target_list",
                         matlab_script_input.values(),
                         ids=matlab_script_input.keys())
def test_matlab_script(program, post_action, node_count, action_count, target_list):
    env = SCons.Environment.Environment()
    expected_string = f'cd ${{TARGET.dir.abspath}} && {program} ${{matlab_options}} -batch ' \
                          '"path(path, \'${SOURCE.dir.abspath}\'); ' \
                          '[fileList, productList] = matlab.codetools.requiredFilesAndProducts(\'${SOURCE.file}\'); ' \
                          'disp(cell2table(fileList)); disp(struct2table(productList, \'AsArray\', true)); exit;" ' \
                          '> ${TARGET.filebase}.matlab.env 2>&1\n' \
                      f'cd ${{TARGET.dir.abspath}} && {program} ${{matlab_options}} -batch ' \
                          '"path(path, \'${SOURCE.dir.abspath}\'); ' \
                          '${SOURCE.filebase}(${script_options})\" ' \
                          '> ${TARGET.filebase}.stdout 2>&1'

    env.Append(BUILDERS={"MatlabScript": scons_extensions.matlab_script(program, post_action)})
    nodes = env.MatlabScript(target=target_list, source=["matlab_script.py"], script_options="")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)

    # TODO: Remove the **kwargs and <name>_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    env.Append(BUILDERS={"MatlabScriptDeprecatedKwarg": scons_extensions.matlab_script(matlab_program=program, post_action=post_action)})
    nodes = env.MatlabScriptDeprecatedKwarg(target=target_list, source=["matlab_script.py"], script_options="")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)


@pytest.mark.unittest
def test_conda_environment():
    env = SCons.Environment.Environment()
    env.Append(BUILDERS={"CondaEnvironment": scons_extensions.conda_environment()})
    nodes = env.CondaEnvironment(
        target=["environment.yaml"], source=[], conda_env_export_options="")
    expected_string = 'cd ${TARGET.dir.abspath} && conda env export ${conda_env_export_options} --file ${TARGET.file}'
    check_action_string(nodes, [], 1, 1, expected_string)


source_file = fs.File("dummy.odb")
abaqus_extract_emitter_input = {
    "empty targets": (
        [],
        [source_file],
        ["dummy.h5", "dummy_datasets.h5", "dummy.csv"],
        {}
    ),
    "one target": (
        ["new_name.h5"],
        [source_file],
        ["new_name.h5", "new_name_datasets.h5", "new_name.csv"],
        {}
    ),
    "bad extension": (
        ["new_name.txt"],
        [source_file],
        ["dummy.h5", "new_name.txt", "dummy_datasets.h5", "dummy.csv"],
        {}
    ),
    "subdirectory": (
        ["set1/dummy.h5"],
        [source_file],
        ["set1/dummy.h5", f"set1{os.sep}dummy_datasets.h5", f"set1{os.sep}dummy.csv"],
        {}
    ),
    "subdirectory new name": (
        ["set1/new_name.h5"],
        [source_file],
        ["set1/new_name.h5", f"set1{os.sep}new_name_datasets.h5", f"set1{os.sep}new_name.csv"],
        {}
    ),
    "one target delete report": (
        ["new_name.h5"],
        [source_file],
        ["new_name.h5", "new_name_datasets.h5"],
        {"delete_report_file": True}
    ),
    "subdirectory delete report": (
        ["set1/dummy.h5"],
        [source_file],
        ["set1/dummy.h5", f"set1{os.sep}dummy_datasets.h5"],
        {"delete_report_file": True}
    ),
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, source, expected, env",
                         abaqus_extract_emitter_input.values(),
                         ids=abaqus_extract_emitter_input.keys())
def test_abaqus_extract_emitter(target, source, expected, env):
    target, source = scons_extensions._abaqus_extract_emitter(target, source, env)
    assert target == expected


@pytest.mark.unittest
def test_abaqus_extract():
    env = SCons.Environment.Environment()
    env.Append(BUILDERS={"AbaqusExtract": scons_extensions.abaqus_extract()})
    nodes = env.AbaqusExtract(
        target=["abaqus_extract.h5"], source=["abaqus_extract.odb"], journal_options="")
    expected_string = '_build_odb_extract(target, source, env)'
    check_action_string(nodes, [], 3, 1, expected_string)


source_file = fs.File("/dummy.source")
target_file = fs.File("/dummy.target")
build_odb_extract_input = {
    "no kwargs": ([target_file], [source_file], {"program": "NA"},
                  [call([f"{root_fs}dummy.source"], f"{root_fs}dummy.target", output_type="h5", odb_report_args=None,
                       abaqus_command="NA", delete_report_file=False)]),
    "all kwargs": ([target_file], [source_file],
                   {"program": "NA", "output_type": "different", "odb_report_args": "notnone",
                    "delete_report_file": True},
                   [call([f"{root_fs}dummy.source"], f"{root_fs}dummy.target", output_type="different", odb_report_args="notnone",
                        abaqus_command="NA", delete_report_file=True)])
}


@pytest.mark.unittest
@pytest.mark.parametrize("target, source, env, calls",
                         build_odb_extract_input.values(),
                         ids=build_odb_extract_input.keys())
def test_build_odb_extract(target, source, env, calls):
    with patch("waves.abaqus.odb_extract.odb_extract") as mock_odb_extract, \
         patch("pathlib.Path.unlink") as mock_unlink:
        scons_extensions._build_odb_extract(target, source, env)
    mock_odb_extract.assert_has_calls(calls)
    mock_unlink.assert_has_calls([call(missing_ok=True)])
    assert mock_unlink.call_count == len(target)


# TODO: Figure out how to cleanly reset the construction environment between parameter sets instead of passing a new
# target per set.
sbatch_input = {
    "default behavior": ("sbatch", [], 2, 1, ["target1.out"]),
    "different command": ("dummy", [], 2, 1, ["target2.out"]),
    "post action": ("sbatch", ["post action"], 2, 1, ["target3.out"])
}


@pytest.mark.unittest
@pytest.mark.parametrize("program, post_action, node_count, action_count, target_list",
                         sbatch_input.values(),
                         ids=sbatch_input.keys())
def test_sbatch(program, post_action, node_count, action_count, target_list):
    env = SCons.Environment.Environment()
    expected_string = f'cd ${{TARGET.dir.abspath}} && {program} --wait --output=${{TARGET.filebase}}.stdout ' \
                       '${slurm_options} --wrap "${slurm_job}"'

    env.Append(BUILDERS={"SlurmSbatch": scons_extensions.sbatch(program, post_action)})
    nodes = env.SlurmSbatch(target=target_list, source=["source.in"], slurm_options="",
                            slurm_job="echo $SOURCE > $TARGET")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)

    # TODO: Remove the **kwargs and <name>_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    env.Append(BUILDERS={"SlurmSbatchDeprecatedKwarg": scons_extensions.sbatch(sbatch_program=program, post_action=post_action)})
    nodes = env.SlurmSbatchDeprecatedKwarg(target=target_list, source=["source.in"], slurm_options="",
                            slurm_job="echo $SOURCE > $TARGET")
    check_action_string(nodes, post_action, node_count, action_count, expected_string)


scanner_input = {                                   # content,       expected_dependencies
    'has_suffix':             ('**\n*INCLUDE, INPUT=dummy.inp',               ['dummy.inp']),
    'no_suffix':              ('**\n*INCLUDE, INPUT=dummy.out',               ['dummy.out']),
    'pattern_not_found':      ( '**\n*DUMMY, STRING=dummy.out',                          []),
    'multiple_files':     ('**\n*INCLUDE, INPUT=dummy.out\n**'
                              '**\n*INCLUDE, INPUT=dummy2.inp', ['dummy.out', 'dummy2.inp']),
    'lower_case':             ('**\n*include, input=dummy.out',               ['dummy.out']),
    'mixed_case':             ('**\n*inClUdE, iNpuT=dummy.out',               ['dummy.out']),
    'no_leading':                 ('*INCLUDE, INPUT=dummy.out',               ['dummy.out']),
    'comment':                   ('**INCLUDE, INPUT=dummy.out'
                              '\n***INCLUDE, INPUT=dummy2.inp',                          []),
    'mixed_keywords':     ('**\n*INCLUDE, INPUT=dummy.out\n**'
                                  '\n*DUMMY, INPUT=dummy2.inp',               ['dummy.out']),
    'trailing_whitespace': ('**\n*INCLUDE, INPUT=dummy.out   ',               ['dummy.out']),
    'extra_space':         ('**\n*INCLUDE,    INPUT=dummy.out',               ['dummy.out']),
}


@pytest.mark.unittest
@pytest.mark.parametrize("content, expected_dependencies",
                         scanner_input.values(),
                         ids=scanner_input.keys())
def test_abaqus_input_scanner(content, expected_dependencies):
    """Tests the expected dependencies based on the mocked content of the file.

    This function does NOT test for recursion.

    :param str content: Mocked content of the file
    :param list expected_dependencies: List of the expected dependencies
    """
    mock_file = unittest.mock.Mock()
    mock_file.get_text_contents.return_value = content
    env = SCons.Environment.Environment()
    scanner = scons_extensions.abaqus_input_scanner()
    dependencies = scanner(mock_file, env)
    found_files = [file.name for file in dependencies]
    assert set(found_files) == set(expected_dependencies)


sphinx_scanner_input = {
     # Test name, content, expected_dependencies
    'include directive': ('.. include:: dummy.txt', ['dummy.txt']),
    'literalinclude directive': ('.. literalinclude:: dummy.txt', ['dummy.txt']),
    'image directive': ( '.. image:: dummy.png',  ['dummy.png']),
    'figure directive': ( '.. figure:: dummy.png',  ['dummy.png']),
    'bibliography directive': ( '.. figure:: dummy.bib', ['dummy.bib']),
    'no match': ('.. notsuppored:: notsupported.txt', []),
    'indented': ('.. only:: html\n\n   .. include:: dummy.txt', ['dummy.txt']),
    'one match multiline': ('.. include:: dummy.txt\n.. notsuppored:: notsupported.txt', ['dummy.txt']),
    'three match multiline': ('.. include:: dummy.txt\n.. figure:: dummy.png\n.. bibliography:: dummy.bib',
                              ['dummy.txt', 'dummy.png', 'dummy.bib'])
}


@pytest.mark.unittest
@pytest.mark.parametrize("content, expected_dependencies",
                         sphinx_scanner_input.values(),
                         ids=sphinx_scanner_input.keys())
def test_sphinx_scanner(content, expected_dependencies):
    mock_file = unittest.mock.Mock()
    mock_file.get_text_contents.return_value = content
    env = SCons.Environment.Environment()
    scanner = scons_extensions.sphinx_scanner()
    dependencies = scanner(mock_file, env)
    found_files = [file.name for file in dependencies]
    assert set(found_files) == set(expected_dependencies)
