#! /usr/bin/env python

import os
import pathlib

from waves import __version__
print(__version__)

# ========================================================================================================= SETTINGS ===
# Set project meta variables
documentation_source_dir = 'docs'
package_source_dir = 'waves'
project_variables = {
    'project_dir': Dir('.').abspath,
    'version': __version__,
    'tutorials_dir': 'tutorials',
    'eabm_dir': 'eabm_package',
    'abaqus_dir': 'eabm_package/abaqus',
    'argparse_types_dir': 'eabm_package/argparse_types',
    'cubit_dir': 'eabm_package/cubit',
    'python_dir': 'eabm_package/python'
}

# ============================================================================================= COMMAND LINE OPTIONS ===
AddOption(
    "--build-dir",
    dest="variant_dir_base",
    default="build",
    nargs=1,
    type="string",
    action="store",
    metavar="DIR",
    help="SCons build (variant) root directory. Relative or absolute path. (default: '%default')"
)
AddOption(
    "--ignore-documentation",
    dest="ignore_documentation",
    default=False,
    action="store_true",
    help="Boolean to ignore the documentation build, e.g. during Conda package build and testing. Unaffected by the " \
         "'--unconditional-build' option. (default: '%default')"
)
AddOption(
    "--unconditional-build",
    dest="unconditional_build",
    default=False,
    action="store_true",
    help="Boolean to force building of conditionally ignored targets, e.g. if the target's action program is missing" \
            " and it would normally be ignored. (default: '%default')"
)
AddOption(
    "--cov-report",
    dest="coverage_report",
    default=False,
    action="store_true",
    help="Boolean to add the coverage report options to the pytest alias (default: '%default')"
)

# ========================================================================================= CONSTRUCTION ENVIRONMENT ===
# Inherit user's full environment and set project options
env = Environment(
    ENV=os.environ.copy(),
    variant_dir_base=GetOption("variant_dir_base"),
    ignore_documentation=GetOption("ignore_documentation"),
    unconditional_build=GetOption("unconditional_build"),
    coverage_report=GetOption("coverage_report")
)

# Find required programs for conditional target ignoring
required_programs = ['sphinx-build']
conf = env.Configure()
for program in required_programs:
    env[program.replace('-', '_')] = conf.CheckProg(program)
conf.Finish()

# Build variable substitution dictionary
project_substitution_dictionary = dict()
for key, value in project_variables.items():
    env[key] = value
    project_substitution_dictionary[f"@{key}@"] = value

# ======================================================================================= SCONSTRUCT LOCAL VARIABLES ===
# Build path object for extension and re-use
variant_dir_base = pathlib.Path(env['variant_dir_base'])

# ========================================================================================================== TARGETS ===
# Add documentation target
if not env['ignore_documentation']:
    build_dir = variant_dir_base / documentation_source_dir
    source_dir = documentation_source_dir
    SConscript(dirs=documentation_source_dir,
               variant_dir=str(build_dir),
               exports=['env', 'project_substitution_dictionary'])
else:
    print(f"The 'ignore_documentation' option was set to 'True'. Skipping documentation SConscript file(s)")

# Add pytests
SConscript(dirs=".", exports='env', duplicate=False)

# ============================================================================================= PROJECT HELP MESSAGE ===
# Add aliases to help message so users know what build target options are available
# This must come *after* all expected Alias definitions and SConscript files.
from SCons.Node.Alias import default_ans
alias_help = "\nTarget Aliases:\n"
for alias in default_ans:
    alias_help += f"    {alias}\n"
Help(alias_help, append=True)
