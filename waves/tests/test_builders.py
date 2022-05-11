"""Test WAVES SCons builders and support functions"""

import pathlib
import pytest

import SCons.Node.FS

from waves import builders


fs = SCons.Node.FS.FS()
source_file = fs.File('dummy.py')
journal_emitter_input = {
    'empty targets': ([],
                      [source_file],
                      ['dummy.jnl', 'dummy.log']),
    'one target': (['dummy.cae'],
                   [source_file],
                   ['dummy.cae', 'dummy.jnl', 'dummy.log'])
}


@pytest.mark.unittest
@pytest.mark.parametrize('target, source, expected',
                         journal_emitter_input.values(),
                         ids=journal_emitter_input.keys())
def test__abaqus_journal_emitter(target, source, expected):
    target, source = builders._abaqus_journal_emitter(target, source, None)
    assert target == expected


@pytest.mark.unittest
def test__abaqus_journal():
    env = SCons.Environment.Environment()
    env.Append(BUILDERS={'AbaqusJournal': builders.abaqus_journal()})
    # TODO: Figure out how to inspect a builder's action definition after creating the associated target.
    node = env.AbaqusJournal(target=['journal.cae'], source=['journal.py'], journal_options="")


fs = SCons.Node.FS.FS()
source_file = fs.File('root.inp')
solver_emitter_input = {
    'empty targets': ('job',
                      [],
                      [source_file],
                      ['job.log', 'job.odb', 'job.dat', 'job.msg', 'job.com', 'job.prt']),
    'one targets': ('job',
                    ['job.sta'],
                    [source_file],
                    ['job.sta', 'job.log', 'job.odb', 'job.dat', 'job.msg', 'job.com', 'job.prt']),
}


@pytest.mark.unittest
@pytest.mark.parametrize('job_name, target, source, expected',
                         solver_emitter_input.values(),
                         ids=solver_emitter_input.keys())
def test__abaqus_solver_emitter(job_name, target, source, expected):
    env = SCons.Environment.Environment()
    env['job_name'] = job_name
    builders._abaqus_solver_emitter(target, source, env)
    assert target == expected


copy_substitute_input = {
    'strings': (['dummy', 'dummy2.in'],
                ['dummy', 'dummy2.in', 'dummy2']),
    'pathlib.Path()s': ([pathlib.Path('dummy'), pathlib.Path('dummy2.in')],
                        ['dummy', 'dummy2.in', 'dummy2']),
}


@pytest.mark.unittest
@pytest.mark.parametrize('source_list, expected_list',
                         copy_substitute_input.values(),
                         ids=copy_substitute_input.keys())
def test__copy_substitute(source_list, expected_list):
    target_list = builders.copy_substitute(source_list, {})
    target_files = [str(target) for target in target_list]
    assert target_files == expected_list
