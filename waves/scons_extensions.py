#! /usr/bin/env python

import pathlib
import re

import SCons.Defaults
import SCons.Builder
import SCons.Environment
import SCons.Node
import SCons.Scanner

from waves.abaqus import odb_extract
from waves._settings import _abaqus_environment_extension
from waves._settings import _abaqus_datacheck_extensions
from waves._settings import _abaqus_explicit_extensions
from waves._settings import _abaqus_standard_extensions
from waves._settings import _abaqus_solver_common_suffixes
from waves._settings import _scons_substfile_suffix
from waves._settings import _stdout_extension
from waves._settings import _cd_action_prefix
from waves._settings import _matlab_environment_extension
from waves._settings import _sierra_environment_extension


# TODO: Remove the **kwargs check and warning for v1.0.0 release
# https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
def _warn_kwarg_change(kwargs, old_kwarg, new_kwarg="program"):
    """Return the value of an old kwarg and raise a deprecation warning pointing to the new kwarg

    Return None if the old keyword argument is not found in the keyword arguments dictionary.

    >>> def function_with_kwarg_change(new_kwarg="something", **kwargs):
    >>>     old_kwarg = waves.scons_extensions._warn_kwarg_change()
    >>>     new_kwarg = old_kwarg if old_kwarg is not None else new_kwarg

    :param dict kwargs: The ``**kwargs`` dictionary from a function interface
    :param str old_kwarg: The older kwarg key.

    :return: Value of the ``old_kwarg`` if it exists in the ``kwargs`` dictionary. ``None`` if the old keyword isn't
        found in the dictionary.
    """
    program = None
    if old_kwarg in kwargs:
        import warnings
        warnings.filterwarnings('always')
        message = f"The '{old_kwarg}' keyword argument will be deprecated in a future version. " \
                  f"Use the '{new_kwarg}' keyword argument instead."
        warnings.warn(message, DeprecationWarning)
        program = kwargs[old_kwarg]
    return program


def project_help_message(env=None, append=True):
    """Add default targets and alias lists to project help message

    See the `SCons Help`_ documentation for appending behavior. Thin wrapper around

    * :meth:`waves.scons_extensions.default_targets_message`
    * :meth:`waves.scons_extensions.alias_list_message`

    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify
    :param bool append: append to the ``env.Help`` message (default). When False, the ``env.Help`` message will be
        overwritten if ``env.Help`` has not been previously called.
    """
    default_targets_message(env=env, append=append)
    alias_list_message(env=env, append=append)


def default_targets_message(env=None, append=True):
    """Add a default targets list to the project's help message

    See the `SCons Help`_ documentation for appending behavior. Adds text to the project help message formatted as

    .. code-block::

       Default Targets:
           Default_Target_1
           Default_Target_2

    where the targets are recovered from ``SCons.Script.DEFAULT_TARGETS``.

    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify
    :param bool append: append to the ``env.Help`` message (default). When False, the ``env.Help`` message will be
        overwritten if ``env.Help`` has not been previously called.
    """
    import SCons.Script  # Required to get a full construction environment
    if not env:
        env = SCons.Environment.Environment()
    default_targets_help = "\nDefault Targets:\n"
    for target in SCons.Script.DEFAULT_TARGETS:
        default_targets_help += f"    {str(target)}\n"
    env.Help(default_targets_help, append=append)


def alias_list_message(env=None, append=True):
    """Add the alias list to the project's help message

    See the `SCons Help`_ documentation for appending behavior. Adds text to the project help message formatted as

    .. code-block::

       Target Aliases:
           Alias_1
           Alias_2

    where the aliases are recovered from ``SCons.Node.Alias.default_ans``.

    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify
    :param bool append: append to the ``env.Help`` message (default). When False, the ``env.Help`` message will be
        overwritten if ``env.Help`` has not been previously called.
    """
    import SCons.Script  # Required to get a full construction environment
    if not env:
        env = SCons.Environment.Environment()
    alias_help = "\nTarget Aliases:\n"
    for alias in SCons.Node.Alias.default_ans:
        alias_help += f"    {alias}\n"
    env.Help(alias_help, append=append)


def append_env_path(program, env):
    """Append SCons contruction environment ``PATH`` with the program's parent directory

    Raises a ``FileNotFoundError`` if the ``program`` absolute path does not exist. Uses the `SCons AppendENVPath`_
    method. If the program parent directory is already on ``PATH``, the ``PATH`` directory order is preserved.

    .. code-block::
       :caption: Example environment modification

       import waves

       env = Environment()
       env["program"] = waves.scons_extensions.find_program(["program"], env)
       if env["program"]:
           waves.append_env_path(env["program"], env)

    :param str program: An absolute path for the program to add to SCons construction environment ``PATH``
    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify
    """
    program = pathlib.Path(program).resolve()
    if not program.exists():
        raise FileNotFoundError(f"The program '{program}' does not exist.")
    env.AppendENVPath("PATH", str(program.parent), delete_existing=False)


def substitution_syntax(substitution_dictionary, prefix="@", postfix="@"):
    """Return a dictionary copy with the pre/postfix added to the key strings

    Assumes a flat dictionary with keys of type str. Keys that aren't strings will be converted to their string
    representation. Nested dictionaries can be supplied, but only the first layer keys will be modified. Dictionary
    values are unchanged.

    :param dict substitution_dictionary: Original dictionary to copy
    :param string prefix: String to prepend to all dictionary keys
    :param string postfix: String to append to all dictionary keys

    :return: Copy of the dictionary with key strings modified by the pre/posfix
    :rtype: dict
    """
    return {f"{prefix}{key}{postfix}": value for key, value in substitution_dictionary.items()}


def _quote_spaces_in_path(path):
    """Traverse parts of a path and place in double quotes if there are spaces in the part

    >>> import pathlib
    >>> import waves
    >>> path = pathlib.Path("path/directory with space/filename.ext")
    >>> waves.scons_extensions._quote_spaces_in_path(path)
    PosixPath('path/"directory with space"/filename.ext')

    :param pathlib.Path path: path to modify as necessary

    :return: Path with parts wrapped in double quotes as necessary
    :rtype: pathlib.Path
    """
    path = pathlib.Path(path)
    new_path = pathlib.Path(path.root)
    for part in path.parts:
        if " " in part:
            part = f'"{part}"'
        new_path = new_path / part
    return new_path


def find_program(names, env):
    """Search for a program from a list of possible program names.

    Returns the absolute path of the first program name found. If path parts contain spaces, the part will be wrapped in
    double quotes.

    :param list names: list of string program names. May include an absolute path.
    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify

    :return: Absolute path of the found program. None if none of the names are found.
    :rtype: str
    """
    if isinstance(names, str):
        names = [names]
    conf = env.Configure()
    program_paths = []
    for name in names:
        program_paths.append(conf.CheckProg(name))
    conf.Finish()
    # Return first non-None path. Default to None if no program path was found.
    first_found_path = next((path for path in program_paths if path is not None), None)
    if first_found_path:
        first_found_path = str(_quote_spaces_in_path(first_found_path))
    return first_found_path


def add_program(names, env):
    """Search for a program from a list of possible program names. Add first found to system ``PATH``.

    Returns the absolute path of the first program name found. Appends ``PATH`` with first program's parent directory
    if a program is found and the directory is not already on ``PATH``. Returns None if no program name is found.

    .. code-block::
       :caption: Example search for an executable named "program"

       import waves

       env = Environment()
       env["program"] = waves.scons_extensions.add_program(["program"], env)

    :param list names: list of string program names. May include an absolute path.
    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify

    :return: Absolute path of the found program. None if none of the names are found.
    :rtype: str
    """
    first_found_path = find_program(names, env)
    if first_found_path:
        append_env_path(first_found_path, env)
    return first_found_path


def add_cubit(names, env):
    """Modifies environment variables with the paths required to ``import cubit`` in a Python3 environment.

    Returns the absolute path of the first program name found. Appends ``PATH`` with first program's parent directory if
    a program is found and the directory is not already on ``PATH``. Prepends ``PYTHONPATH`` with ``parent/bin``.
    Prepends ``LD_LIBRARY_PATH`` with ``parent/bin/python3``.

    Returns None if no program name is found.

    .. code-block::
       :caption: Example Cubit environment modification

       import waves

       env = Environment()
       env["cubit"] = waves.scons_extensions.add_cubit(["cubit"], env)

    :param list names: list of string program names. May include an absolute path.
    :param SCons.Script.SConscript.SConsEnvironment env: The SCons construction environment object to modify

    :return: Absolute path of the found program. None if none of the names are found.
    :rtype: str
    """
    first_found_path = add_program(names, env)
    if first_found_path:
        cubit_program = pathlib.Path(first_found_path)
        cubit_python_dir = cubit_program.parent / "bin"
        cubit_python_library_dir = cubit_python_dir / "python3"
        env.PrependENVPath("PYTHONPATH", str(cubit_python_dir))
        env.PrependENVPath("LD_LIBRARY_PATH", str(cubit_python_library_dir))
    return first_found_path


def _construct_post_action_list(post_action):
    """Return a post-action list

    Returns the constructed post-action list of strings with prepended directory change as

    .. code-block::

       f"cd ${{TARGET.dir.abspath}} && {new_action}"

    where action objects are converted to their string representation. If a string is passed instead of a list, it is
    first convert to a list. Other string-like objects, e.g. bytes, are not converted, but iterated on
    character-by-character. If an empty list is passed, and empty list is returned.

    :param list post_action: List of post-action strings

    :return: post-action list of strings
    :rtype: list
    """
    if isinstance(post_action, str):
        post_action = [post_action]
    try:
        iterator = iter(post_action)
    except TypeError:
        iterator = iter([post_action])
    new_actions = [f"{_cd_action_prefix} {action}" for action in iterator]
    return new_actions


def _build_subdirectory(target):
    """Return the build subdirectory of the first target file

    :param list target: The target file list of strings

    :return: build directory
    :rtype: pathlib.Path
    """
    try:
        build_subdirectory = pathlib.Path(str(target[0])).parents[0]
    except IndexError as err:
        build_subdirectory = pathlib.Path(".")
    return build_subdirectory


def _first_target_emitter(target, source, env, suffixes=None):
    """Appends the target list with the builder managed targets

    Appends ``target[0]``.stdout to the ``target`` list. The associated Builder requires at least one target.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``target[0].stdout``.

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object

    :return: target, source
    :rtype: tuple with two lists
    """
    if not suffixes:
        suffixes = [_stdout_extension]
    build_subdirectory = _build_subdirectory(target)
    first_target = pathlib.Path(str(target[0]))
    for suffix in suffixes:
        emitter_target = str(build_subdirectory / first_target.with_suffix(suffix).name)
        if emitter_target not in target:
            target.append(emitter_target)
    return target, source


def _abaqus_journal_emitter(target, source, env):
    """Appends the abaqus_journal builder target list with the builder managed targets

    Appends ``target[0]``.stdout and ``target[0]``.abaqus_v6.env to the ``target`` list. The abaqus_journal Builder
    requires at least one target.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``target[0].stdout``.

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object

    :return: target, source
    :rtype: tuple with two lists
    """
    suffixes = [_stdout_extension, _abaqus_environment_extension]
    return _first_target_emitter(target, source, env, suffixes=suffixes)


def abaqus_journal(program="abaqus", post_action=None, **kwargs):
    """Abaqus journal file SCons builder

    This builder requires that the journal file to execute is the first source in the list. The builder returned by this
    function accepts all SCons Builder arguments and adds the keyword argument(s):

    * ``journal_options``: The journal file command line options provided as a string.
    * ``abaqus_options``: The Abaqus command line options provided as a string.

    At least one target must be specified. The first target determines the working directory for the builder's action,
    as shown in the action code snippet below. The action changes the working directory to the first target's parent
    directory prior to executing the journal file.

    The Builder emitter will append the builder managed targets automatically. Appends ``target[0]``.stdout and
    ``target[0]``.abaqus_v6.env to the ``target`` list.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/my_target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``my_target.stdout``.

    .. code-block::
       :caption: Abaqus journal builder action

       cd ${TARGET.dir.abspath} && abaqus cae -noGui ${SOURCE.abspath} ${abaqus_options} -- ${journal_options} > ${TARGET.filebase}.stdout 2>&1

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={"AbaqusJournal": waves.scons_extensions.abaqus_journal()})
       AbaqusJournal(target=["my_journal.cae"], source=["my_journal.py"], journal_options="")

    :param str program: An absolute path or basename string for the abaqus program.
    :param list post_action: List of shell command string(s) to append to the builder's action list. Implemented to
        allow post target modification or introspection, e.g. inspect the Abaqus log for error keywords and throw a
        non-zero exit code even if Abaqus does not. Builder keyword variables are available for substitution in the
        ``post_action`` action using the ``${}`` syntax. Actions are executed in the first target's directory as ``cd
        ${TARGET.dir.abspath} && ${post_action}``

    :return: Abaqus journal builder
    :rtype: SCons.Builder.Builder
    """
    # TODO: Remove the **kwargs and abaqus_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    abaqus_program = _warn_kwarg_change(kwargs, "abaqus_program")
    program = abaqus_program if abaqus_program is not None else program
    if not post_action:
        post_action = []
    action = [f"{_cd_action_prefix} {program} -information environment > " \
                 f"${{TARGET.filebase}}{_abaqus_environment_extension}",
              f"{_cd_action_prefix} {program} cae -noGui ${{SOURCE.abspath}} ${{abaqus_options}} -- " \
                 f"${{journal_options}} > ${{TARGET.filebase}}{_stdout_extension} 2>&1"]
    action.extend(_construct_post_action_list(post_action))
    abaqus_journal_builder = SCons.Builder.Builder(
        action=action,
        emitter=_abaqus_journal_emitter)
    return abaqus_journal_builder


def _abaqus_solver_emitter(target, source, env, suffixes_to_extend=None):
    """Appends the abaqus_solver builder target list with the builder managed targets

    If no targets are provided to the Builder, the emitter will assume all emitted targets build in the current build
    directory. If the target(s) must be built in a build subdirectory, e.g. in a parameterized target build, then at
    least one target must be provided with the build subdirectory, e.g. ``parameter_set1/target.ext``. When in doubt,
    provide the output database as a target, e.g. ``job_name.odb``

    If "suffixes" is a key in the environment, ``env``, then the suffixes list will override the ``suffixes_to_extend``
    argument.

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object
    :param list suffixes_to_extend: List of strings to use as emitted file suffixes. Must contain the leading period,
        e.g. ``.extension``

    :return: target, source
    :rtype: tuple with two lists
    """
    if "suffixes" in env and env["suffixes"] is not None:
        suffixes_to_extend = env["suffixes"]
    elif not suffixes_to_extend:
        suffixes_to_extend = _abaqus_solver_common_suffixes
    if "job_name" not in env or not env["job_name"]:
        env["job_name"] = pathlib.Path(source[0].path).stem
    suffixes = [_stdout_extension, _abaqus_environment_extension]
    if isinstance(suffixes_to_extend, str):
        suffixes_to_extend = [suffixes_to_extend]
    suffixes.extend(suffixes_to_extend)
    build_subdirectory = _build_subdirectory(target)
    for suffix in suffixes:
        emitter_target = str(build_subdirectory / f"{env['job_name']}{suffix}")
        if emitter_target not in target:
            target.append(emitter_target)
    return target, source


def _abaqus_standard_solver_emitter(target, source, env):
    """Passes the standard specific extensions to :meth:`_abaqus_solver_emitter`"""
    return _abaqus_solver_emitter(target, source, env, _abaqus_standard_extensions)


def _abaqus_explicit_solver_emitter(target, source, env):
    """Passes the explicit specific extensions to :meth:`_abaqus_solver_emitter`"""
    return _abaqus_solver_emitter(target, source, env, _abaqus_explicit_extensions)


def _abaqus_datacheck_solver_emitter(target, source, env):
    """Passes the datacheck specific extensions to :meth:`_abaqus_solver_emitter`"""
    return _abaqus_solver_emitter(target, source, env, _abaqus_datacheck_extensions)


def abaqus_solver(program="abaqus", post_action=None, emitter=None, **kwargs):
    """Abaqus solver SCons builder

    This builder requires that the root input file is the first source in the list. The builder returned by this
    function accepts all SCons Builder arguments and adds the keyword argument(s):

    * ``job_name``: The job name string. If not specified ``job_name`` defaults to the root input file stem. The Builder
      emitter will append common Abaqus output files as targets automatically from the ``job_name``, e.g. ``job_name.odb``.
    * ``abaqus_options``: The Abaqus command line options provided as a string.
    * ``suffixes``: override the emitter targets with a new list of extensions, e.g.
      ``AbaqusSolver(target=[], source=["input.inp"], suffixes=[".odb"])`` will emit only one file named
      ``job_name.odb``.

    The first target determines the working directory for the builder's action, as shown in the action code snippet
    below. The action changes the working directory to the first target's parent directory prior to executing the
    journal file.

    This builder is unique in that no targets are required. The Builder emitter will append the builder managed targets
    automatically. The target list only appends those extensions which are common to Abaqus analysis operations. Some
    extensions may need to be added explicitly according to the Abaqus simulation solver, type, or options. If you find
    that SCons isn't automatically cleaning some Abaqus output files, they are not in the automatically appended target
    list.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/job_name.odb``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``my_target.stdout``.

    The ``-interactive`` option is always appended to the builder action to avoid exiting the Abaqus task before the
    simulation is complete.  The ``-ask_delete no`` option is always appended to the builder action to overwrite
    existing files in programmatic execution, where it is assumed that the Abaqus solver target(s) should be re-built
    when their source files change.

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={
           "AbaqusSolver": waves.scons_extensions.abaqus_solver(),
           "AbaqusStandard": waves.scons_extensions.abaqus_solver(emitter='standard'),
           "AbaqusOld": waves.scons_extensions.abaqus_solver(program="abq2019"),
           "AbaqusPost": waves.scons_extensions.abaqus_solver(post_action="grep -E "\<SUCCESSFULLY" ${job_name}.sta")
       })
       AbaqusSolver(target=[], source=["input.inp"], job_name="my_job", abaqus_options="-cpus 4")
       AbaqusSolver(target=[], source=["input.inp"], job_name="my_job", suffixes=[".odb"])

    .. code-block::
       :caption: Abaqus journal builder action

       cd ${TARGET.dir.abspath} && ${program} -job ${job_name} -input ${SOURCE.filebase} ${abaqus_options} -interactive -ask_delete no > ${job_name}.stdout 2>&1

    :param str program: An absolute path or basename string for the abaqus program
    :param list post_action: List of shell command string(s) to append to the builder's action list. Implemented to
        allow post target modification or introspection, e.g. inspect the Abaqus log for error keywords and throw a
        non-zero exit code even if Abaqus does not. Builder keyword variables are available for substitution in the
        ``post_action`` action using the ``${}`` syntax. Actions are executed in the first target's directory as ``cd
        ${TARGET.dir.abspath} && ${post_action}``.
    :param str emitter: emit file extensions based on the value of this variable. Overridden by the ``suffixes`` keyword
        argument that may be provided in the Task definition.

        * "standard": [".odb", ".dat", ".msg", ".com", ".prt", ".sta"]
        * "explicit": [".odb", ".dat", ".msg", ".com", ".prt", ".sta"]
        * "datacheck": [".odb", ".dat", ".msg", ".com", ".prt", ".023", ".mdl", ".sim", ".stt"]
        * default value: [".odb", ".dat", ".msg", ".com", ".prt"]

    :return: Abaqus solver builder
    :rtype: SCons.Builder.Builder
    """
    # TODO: Remove the **kwargs and abaqus_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    abaqus_program = _warn_kwarg_change(kwargs, "abaqus_program")
    program = abaqus_program if abaqus_program is not None else program
    if not post_action:
        post_action = []
    action = [f"{_cd_action_prefix} {program} -information environment > " \
                  f"${{job_name}}{_abaqus_environment_extension}",
              f"{_cd_action_prefix} {program} -job ${{job_name}} -input ${{SOURCE.filebase}} " \
                  f"${{abaqus_options}} -interactive -ask_delete no > ${{job_name}}{_stdout_extension} 2>&1"]
    action.extend(_construct_post_action_list(post_action))
    if emitter:
        emitter = emitter.lower()
    if emitter == 'standard':
        abaqus_emitter = _abaqus_standard_solver_emitter
    elif emitter == 'explicit':
        abaqus_emitter = _abaqus_explicit_solver_emitter
    elif emitter == 'datacheck':
        abaqus_emitter = _abaqus_datacheck_solver_emitter
    else:
        abaqus_emitter = _abaqus_solver_emitter
    abaqus_solver_builder = SCons.Builder.Builder(
        action=action,
        emitter=abaqus_emitter)
    return abaqus_solver_builder


def _sierra_emitter(target, source, env):
    """Appends the sierra builder target list with the builder managed targets

    Appends ``target[0]``.stdout and ``target[0]``.env to the ``target`` list. The Sierra Builder requires
    at least one target.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``target[0].stdout``.

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object

    :return: target, source
    :rtype: tuple with two lists
    """
    suffixes = [_stdout_extension, _sierra_environment_extension]
    return _first_target_emitter(target, source, env, suffixes=suffixes)


def sierra(program="sierra", application="adagio", post_action=None):
    """Sierra SCons builder

    This builder requires that the root input file is the first source in the list. The builder returned by this
    function accepts all SCons Builder arguments and adds the keyword argument(s):

    * ``sierra_options``: The Sierra command line options provided as a string.
    * ``application_options``: The application (e.g. adagio) command line options provided as a string.

    The first target determines the working directory for the builder's action, as shown in the action code snippet
    below. The action changes the working directory to the first target's parent directory prior to executing the
    journal file.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``target[0].stdout``.

    .. warning::

       This is an experimental builder for Sierra support. The only emitted file is the application's version report in
       ``TARGET[0].env`` and the ``TARGET[0].stdout`` redirected STDOUT and STDERR file. All relevant application output
       files, e.g. ``genesis_output.e`` must be specified in the target list.

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={
           "Sierra": waves.scons_extensions.sierra(),
       })
       Sierra(target=["output.e"], source=["input.i"])

    .. code-block::
       :caption: Sierra builder action

       cd ${TARGET.dir.abspath} && ${program} ${sierra_options} ${application} ${application_options} -i ${SOURCE.file} > ${TARGET.filebase}.stdout 2>&1

    :param str program: An absolute path or basename string for the Sierra program
    :param str application: The string name for the Sierra application
    :param list post_action: List of shell command string(s) to append to the builder's action list. Implemented to
        allow post target modification or introspection, e.g. inspect the Sierra log for error keywords and throw a
        non-zero exit code even if Sierra does not. Builder keyword variables are available for substitution in the
        ``post_action`` action using the ``${}`` syntax. Actions are executed in the first target's directory as ``cd
        ${TARGET.dir.abspath} && ${post_action}``.

    :return: Sierra builder
    :rtype: SCons.Builder.Builder
    """
    if not post_action:
        post_action = []
    action = [f"{_cd_action_prefix} {program} {application} --version > " \
                  f"${{TARGET.filebase}}{_sierra_environment_extension}",
              f"{_cd_action_prefix} {program} ${{sierra_options}} {application} ${{application_options}} " \
                  f"-i ${{SOURCE.file}} > ${{TARGET.filebase}}{_stdout_extension} 2>&1"]
    action.extend(_construct_post_action_list(post_action))
    sierra_builder = SCons.Builder.Builder(
        action=action,
        emitter=_sierra_emitter
    )
    return sierra_builder


def copy_substitute(source_list, substitution_dictionary=None, env=SCons.Environment.Environment(),
                    build_subdirectory=".", symlink=False):
    """Copy source list to current variant directory and perform template substitutions on ``*.in`` filenames

    .. warning::

       This is a Python function and not an SCons builder. It cannot be added to the construction environment
       ``BUILDERS`` list. The function returns a list of targets instead of a Builder object.

    Creates an SCons Copy task for each source file. Files are copied to the current variant directory
    matching the calling SConscript parent directory. Files with the name convention ``*.in`` are also given an SCons
    Substfile Builder, which will perform template substitution with the provided dictionary in-place in the current
    variant directory and remove the ``.in`` suffix.

    To avoid dependency cycles, the source file(s) should be passed by absolute path.

    .. code-block::
       :caption: SConstruct

       import pathlib
       import waves
       env = Environment()
       current_directory = pathlib.Path(Dir(".").abspath)
       source_list = [
           "#/subdir3/file_three.ext",              # File found with respect to project root directory using SCons notation
           current_directory / file_one.ext,        # File found in current SConscript directory
           current_directory / "subdir2/file_two",  # File found below current SConscript directory
           current_directory / "file_four.ext.in"   # File with substitutions matching substitution dictionary keys
       ]
       substitution_dictionary = {
           "@variable_one@": "value_one"
       }
       waves.scons_extensions.copy_substitute(source_list, substitution_dictionary, env)

    :param list source_list: List of pathlike objects or strings. Will be converted to list of pathlib.Path objects.
    :param dict substitution_dictionary: key: value pairs for template substitution. The keys must contain the optional
        template characters if present, e.g. ``@variable@``. The template character, e.g. ``@``, can be anything that
        works in the `SCons Substfile`_ builder.
    :param SCons.Environment.Environment env: An SCons construction environment to use when defining the targets.
    :param str build_subdirectory: build subdirectory relative path prepended to target files
    :param bool symlink: Whether symbolic links are created as new symbolic links. If true, symbolic links are shallow
        copies as a new symbolic link. If false, symbolic links are copied as a new file (dereferenced).

    :return: SCons NodeList of Copy and Substfile target nodes
    :rtype: SCons.Node.NodeList
    """
    if not substitution_dictionary:
        substitution_dictionary = {}
    build_subdirectory = pathlib.Path(build_subdirectory)
    target_list = SCons.Node.NodeList()
    source_list = [pathlib.Path(source_file) for source_file in source_list]
    for source_file in source_list:
        copy_target = build_subdirectory / source_file.name
        target_list += env.Command(
                target=str(copy_target),
                source=str(source_file),
                action=SCons.Defaults.Copy("${TARGET}", "${SOURCE}", symlink))
        if source_file.suffix == _scons_substfile_suffix:
            substfile_target = build_subdirectory / source_file.name
            target_list += env.Substfile(str(substfile_target), SUBST_DICT=substitution_dictionary)
    return target_list


def python_script(post_action=None):
    """Python script SCons builder

    This builder requires that the python script to execute is the first source in the list. The builder returned by
    this function accepts all SCons Builder arguments and adds the keyword argument(s):

    * ``script_options``: The Python script command line arguments provided as a string.
    * ``python_options``: The Python command line arguments provided as a string.

    At least one target must be specified. The first target determines the working directory for the builder's action,
    as shown in the action code snippet below. The action changes the working directory to the first target's parent
    directory prior to executing the python script.

    The Builder emitter will append the builder managed targets automatically. Appends ``target[0]``.stdout to the
    ``target`` list.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/my_target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``my_target.stdout``.

    .. code-block::
       :caption: Python script builder action

       cd ${TARGET.dir.abspath} && python ${python_options} ${SOURCE.abspath} ${script_options} > ${TARGET.filebase}.stdout 2>&1

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={"PythonScript": waves.scons_extensions.python_script()})
       PythonScript(target=["my_output.stdout"], source=["my_script.py"], python_options="", script_options="")

    :param list post_action: List of shell command string(s) to append to the builder's action list. Implemented to
        allow post target modification or introspection, e.g. inspect a log for error keywords and throw a
        non-zero exit code even if Python does not. Builder keyword variables are available for substitution in the
        ``post_action`` action using the ``${}`` syntax. Actions are executed in the first target's directory as ``cd
        ${TARGET.dir.abspath} && ${post_action}``

    :return: Python script builder
    :rtype: SCons.Builder.Builder
    """
    if not post_action:
        post_action = []
    action = [f"{_cd_action_prefix} python ${{python_options}} ${{SOURCE.abspath}} " \
                f"${{script_options}} > ${{TARGET.filebase}}{_stdout_extension} 2>&1"]
    action.extend(_construct_post_action_list(post_action))
    python_builder = SCons.Builder.Builder(
        action=action,
        emitter=_first_target_emitter)
    return python_builder


def _matlab_script_emitter(target, source, env):
    """Appends the matlab_script builder target list with the builder managed targets

    Appends ``target[0]``.stdout and ``target[0]``.matlab.env to the ``target`` list. The matlab_script Builder requires
    at least one target. The build tree copy of the Matlab script is not added to the target list to avoid multiply
    defined targets when the script is used more than once in the same build directory.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``target[0].stdout``.

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object

    :return: target, source
    :rtype: tuple with two lists
    """
    suffixes = [_stdout_extension, _matlab_environment_extension]
    return _first_target_emitter(target, source, env, suffixes=suffixes)


def matlab_script(program="matlab", post_action=None, **kwargs):
    """Matlab script SCons builder

    .. warning::

       Experimental implementation is subject to change

    This builder requires that the Matlab script is the first source in the list. The builder returned by this function
    accepts all SCons Builder arguments and adds the keyword argument(s):

    * ``script_options``: The Matlab function interface options in Matlab syntax and provided as a string.
    * ``matlab_options``: The Matlab command line options provided as a string.

    The parent directory absolute path is added to the Matlab ``path`` variable prior to execution. All required Matlab
    files should be co-located in the same source directory.

    At least one target must be specified. The first target determines the working directory for the builder's action,
    as shown in the action code snippet below. The action changes the working directory to the first target's parent
    directory prior to executing the python script.

    The Builder emitter will append the builder managed targets automatically. Appends ``target[0]``.stdout and
    ``target[0].matlab.env to the ``target`` list.

    The emitter will assume all emitted targets build in the current build directory. If the target(s) must be built in
    a build subdirectory, e.g. in a parameterized target build, then the first target must be provided with the build
    subdirectory, e.g. ``parameter_set1/my_target.ext``. When in doubt, provide the expected STDOUT redirected file as a
    target, e.g. ``my_target.stdout``.

    .. code-block::
       :caption: Matlab script builder action

       cd ${TARGET.dir.abspath} && {program} ${matlab_options} -batch "path(path, '${SOURCE.dir.abspath}'); ${SOURCE.filebase}(${script_options})" > ${TARGET.filebase}.stdout 2>&1

    :param str program: An absolute path or basename string for the Matlab program.
    :param list post_action: List of shell command string(s) to append to the builder's action list. Implemented to
        allow post target modification or introspection, e.g. inspect a log for error keywords and throw a
        non-zero exit code even if Matlab does not. Builder keyword variables are available for substitution in the
        ``post_action`` action using the ``${}`` syntax. Actions are executed in the first target's directory as ``cd
        ${TARGET.dir.abspath} && ${post_action}``

    :return: Matlab script builder
    :rtype: SCons.Builder.Builder
    """
    # TODO: Remove the **kwargs and matlab_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    matlab_program = _warn_kwarg_change(kwargs, "matlab_program")
    program = matlab_program if matlab_program is not None else program
    if not post_action:
        post_action = []
    action = [f"{_cd_action_prefix} {program} ${{matlab_options}} -batch " \
                  "\"path(path, '${SOURCE.dir.abspath}'); " \
                  "[fileList, productList] = matlab.codetools.requiredFilesAndProducts('${SOURCE.file}'); " \
                  "disp(cell2table(fileList)); disp(struct2table(productList, 'AsArray', true)); exit;\" " \
                  f"> ${{TARGET.filebase}}{_matlab_environment_extension} 2>&1",
              f"{_cd_action_prefix} {program} ${{matlab_options}} -batch " \
                  "\"path(path, '${SOURCE.dir.abspath}'); " \
                  "${SOURCE.filebase}(${script_options})\" " \
                  f"> ${{TARGET.filebase}}{_stdout_extension} 2>&1"]
    action.extend(_construct_post_action_list(post_action))
    matlab_builder = SCons.Builder.Builder(
        action=action,
        emitter=_matlab_script_emitter)
    return matlab_builder


def conda_environment():
    """Create a Conda environment file with ``conda env export``

    This builder is intended to help WAVES workflows document the Conda environment used in the current build. At least
    one target file must be specified for the ``conda env export --file ${TARGET}`` output. Additional options to the
    Conda ``env export`` subcommand may be passed as the builder keyword argument ``conda_env_export_options``.

    At least one target must be specified. The first target determines the working directory for the builder's action,
    as shown in the action code snippet below. The action changes the working directory to the first target's parent
    directory prior to creating the Conda environment file.

    .. code-block::
       :caption: Conda environment builder action

       cd ${TARGET.dir.abspath} && conda env export ${conda_env_export_options} --file ${TARGET.file}

    The modsim owner may choose to re-use this builder throughout their project configuration to provide various levels
    of granularity in the recorded Conda environment state. It's recommended to include this builder at least once for
    any workflows that also use the :meth:`waves.scons_extensions.python_builder`. The builder may be re-used once per build
    sub-directory to provide more granular build environment reproducibility in the event that sub-builds are run at
    different times with variations in the active Conda environment. For per-Python script task environment
    reproducibility, the builder source list can be linked to the output of a :meth:`waves.scons_extensions.python_builder` task
    with a target environment file name to match.

    The first recommendation, always building the project wide Conda environment file, is demonstrated in the example
    usage below.

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={"CondaEnvironment": waves.scons_extensions.conda_environment()})
       environment_target = env.CondaEnvironment(target=["environment.yaml"])
       env.AlwaysBuild(environment_target)

    :return: Conda environment builder
    :rtype: SCons.Builder.Builder
    """
    conda_environment_builder = SCons.Builder.Builder(
        action=
            [f"{_cd_action_prefix} conda env export ${{conda_env_export_options}} --file ${{TARGET.file}}"])
    return conda_environment_builder


def _abaqus_extract_emitter(target, source, env):
    """Prepends the abaqus extract builder target H5 file if none is specified. Appends the source[0].csv file unless
    ``delete_report_file`` is ``True``.  Always appends the ``target[0]_datasets.h5`` file.

    If no targets are provided to the Builder, the emitter will assume all emitted targets build in the current build
    directory. If the target(s) must be built in a build subdirectory, e.g. in a parameterized target build, then at
    least one target must be provided with the build subdirectory, e.g. ``parameter_set1/target.h5``. When in doubt,
    provide the expected H5 file as a target, e.g. ``source[0].h5``.

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object

    :return: target, source
    :rtype: tuple with two lists
    """
    odb_file = pathlib.Path(source[0].path).name
    odb_file = pathlib.Path(odb_file)
    build_subdirectory = _build_subdirectory(target)
    if not target or pathlib.Path(str(target[0])).suffix != ".h5":
        target.insert(0, str(build_subdirectory / odb_file.with_suffix(".h5")))
    first_target = pathlib.Path(str(target[0]))
    target.append(f"{build_subdirectory / first_target.stem}_datasets.h5")
    if not "delete_report_file" in env or not env["delete_report_file"]:
        target.append(str(build_subdirectory / first_target.with_suffix(".csv").name))
    return target, source


def abaqus_extract(program="abaqus", **kwargs):
    """Abaqus ODB file extraction Builder

    This builder executes the ``odb_extract`` command line utility against an ODB file in the source list. The ODB file
    must be the first file in the source list. If there is more than one ODB file in the source list, all but the first
    file are ignored by ``odb_extract``.

    This builder is unique in that no targets are required. The Builder emitter will append the builder managed targets
    and ``odb_extract`` target name constructions automatically. The first target determines the working directory for
    the emitter targets. If the target(s) must be built in a build subdirectory, e.g. in a parameterized target build,
    then at least one target must be provided with the build subdirectory, e.g. ``parameter_set1/target.h5``. When in
    doubt, provide the expected H5 file as a target, e.g. ``source[0].h5``.

    The target list may specify an output H5 file name that differs from the ODB file base name as ``new_name.h5``. If
    the first file in the target list does not contain the ``*.h5`` extension, or if there is no file in the target
    list, the target list will be prepended with a name matching the ODB file base name and the ``*.h5`` extension.

    The builder emitter appends the CSV file created by the ``abaqus odbreport`` command as executed by
    ``odb_extract`` unless ``delete_report_file`` is set to ``True``.

    This builder supports the keyword arguments: ``output_type``, ``odb_report_args``, ``delete_report_file`` with
    behavior as described in the :ref:`odb_extract_cli` command line interface.

    .. warning::

       ``odb_extract`` *requires* Abaqus arguments for ``odb_report_args`` in the form of ``option=value``, e.g.
       ``step=step_name``.

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={"AbaqusExtract": waves.scons_extensions.abaqus_extract()})
       AbaqusExtract(target=["my_job.h5", "my_job.csv"], source=["my_job.odb"])

    :param str program: An absolute path or basename string for the abaqus program

    :return: Abaqus extract builder
    :rtype: SCons.Builder.Builder
    """
    # TODO: Remove the **kwargs and abaqus_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    abaqus_program = _warn_kwarg_change(kwargs, "abaqus_program")
    program = abaqus_program if abaqus_program is not None else program
    abaqus_extract_builder = SCons.Builder.Builder(
        action = [
            SCons.Action.Action(_build_odb_extract, varlist=["output_type", "odb_report_args", "delete_report_file"])
        ],
        emitter=_abaqus_extract_emitter,
        program=program)
    return abaqus_extract_builder


def _build_odb_extract(target, source, env):
    """Define the odb_extract action when used as an internal package and not a command line utility

    :param list target: The target file list of strings
    :param list source: The source file list of SCons.Node.FS.File objects
    :param SCons.Script.SConscript.SConsEnvironment env: The builder's SCons construction environment object
    """
    # Default odb_extract arguments
    output_type = "h5"
    odb_report_args = None
    delete_report_file = False

    # Grab arguments from environment if they exist
    if "output_type" in env:
        output_type = env["output_type"]
    if "odb_report_args" in env:
        odb_report_args = env["odb_report_args"]
    if "delete_report_file" in env:
        delete_report_file = env["delete_report_file"]

    # Remove existing target files that are not overwritten by odb_extract
    files_to_remove = [pathlib.Path(path.abspath) for path in target]
    for path in files_to_remove:
        path.unlink(missing_ok=True)

    odb_extract.odb_extract([source[0].abspath], target[0].abspath,
                            output_type=output_type,
                            odb_report_args=odb_report_args,
                            abaqus_command=env["program"],
                            delete_report_file=delete_report_file)
    return None


def sbatch(program="sbatch", post_action=None, **kwargs):
    """SLURM sbatch SCons builder

    The builder does not use a SLURM batch script. Instead, it requires the ``slurm_job`` variable to be defined with
    the command string to execute.

    At least one target must be specified. The first target determines the working directory for the builder's action,
    as shown in the action code snippet below. The action changes the working directory to the first target's parent
    directory prior to executing the journal file.

    The Builder emitter will append the builder managed targets automatically. Appends ``target[0]``.stdout to the
    ``target`` list.

    .. code-block::
       :caption: SLURM sbatch builder action

       cd ${TARGET.dir.abspath} && sbatch --wait ${slurm_options} --wrap ${slurm_job} > ${TARGET.filebase}.stdout 2>&1

    .. code-block::
       :caption: SConstruct

       import waves
       env = Environment()
       env.Append(BUILDERS={"SlurmSbatch": waves.scons_extensions.sbatch()})
       SlurmSbatch(target=["my_output.stdout"], source=["my_source.input"], slurm_job="echo $SOURCE > $TARGET")

    :param str program: An absolute path or basename string for the sbatch program.
    :param list post_action: List of shell command string(s) to append to the builder's action list. Implemented to
        allow post target modification or introspection, e.g. inspect the Abaqus log for error keywords and throw a
        non-zero exit code even if Abaqus does not. Builder keyword variables are available for substitution in the
        ``post_action`` action using the ``${}`` syntax. Actions are executed in the first target's directory as ``cd
        ${TARGET.dir.abspath} && ${post_action}``

    :return: SLURM sbatch builder
    :rtype: SCons.Builder.Builder
    """
    # TODO: Remove the **kwargs and sbatch_program check for v1.0.0 release
    # https://re-git.lanl.gov/aea/python-projects/waves/-/issues/508
    sbatch_program = _warn_kwarg_change(kwargs, "sbatch_program")
    program = sbatch_program if sbatch_program is not None else program
    if not post_action:
        post_action = []
    action = [f"{_cd_action_prefix} {program} --wait ${{slurm_options}} --wrap \"${{slurm_job}}\" > " \
                 f"${{TARGET.filebase}}{_stdout_extension} 2>&1"]
    action.extend(_construct_post_action_list(post_action))
    sbatch_builder = SCons.Builder.Builder(
        action=action,
        emitter=_first_target_emitter)
    return sbatch_builder


def abaqus_input_scanner():
    """Abaqus input file dependency scanner

    Custom SCons scanner that searches for ``*INCLUDE`` keyword inside Abaqus ``.inp`` files.

    :return: Abaqus input file dependency Scanner
    :rtype: SCons.Scanner.Scanner
    """
    flags = re.IGNORECASE
    return _custom_scanner(r'^\*INCLUDE,\s*input=(.+)$', ['.inp'], flags)


def sphinx_scanner():
    """SCons scanner that searches for directives

    * ``.. include::``
    * ``.. literalinclude::``
    * ``.. image::``
    * ``.. figure::``
    * ``.. bibliography::``

    inside ``.rst`` and ``.txt`` files

    :return: Abaqus input file dependency Scanner
    :rtype: SCons.Scanner.Scanner
    """
    return _custom_scanner(r'^\s*\.\. (?:include|literalinclude|image|figure|bibliography)::\s*(.+)$', ['.rst', '.txt'])


def _custom_scanner(pattern, suffixes, flags=None):
    """Custom Scons scanner

    constructs a scanner object based on a regular expression pattern. Will only search for files matching the list of
    suffixes provided. ``_custom_scanner`` will always use the ``re.MULTILINE`` flag
    https://docs.python.org/3/library/re.html#re.MULTILINE

    :param str pattern: Regular expression pattern.
    :param list suffixes: List of suffixes of files to search
    :param int flags: An integer representing the combination of re module flags to be used during compilation.
                      Additional flags can be combined using the bitwise OR (|) operator. The re.MULTILINE flag is
                      automatically added to the combination.

    :return: Custom Scons scanner
    :rtype: Scons.Scanner.Scanner
    """
    flags = re.MULTILINE if not flags else re.MULTILINE | flags
    expression = re.compile(pattern, flags)

    def suffix_only(node_list):
        """Recursively search for files that end in the given suffixes

        :param list node_list: List of SCons Node objects representing the nodes to process

        :return: List of file dependencies to include for recursive scanning
        :rtype: list
        """
        return [node for node in node_list if node.path.endswith(tuple(suffixes))]

    def regex_scan(node, env, path):
        """Scan function for extracting dependencies from the content of a file based on the given regular expression.

        The interface of the scan function is fixed by SCons. It must include ``node``, ``env`` and ``path``. It may
        contain additional arguments if needed. For more information please read the SCons Scanner tutorial:
        https://scons.org/doc/1.2.0/HTML/scons-user/c3755.html

        :param SCons.Node.FS node: SCons Node object representing the file to scan
        :param SCons.Environment.Environment env: SCons Environment object
        :param str path: Path argument passed to the scan function

        :return: List of file dependencies found during scanning
        :rtype: list
        """
        contents = node.get_text_contents()
        includes = expression.findall(contents)
        includes = [file.strip() for file in includes]
        return includes

    custom_scanner = SCons.Scanner.Scanner(function=regex_scan, skeys=suffixes, recursive=suffix_only)
    return custom_scanner
