.. _tutorial_include_files_waves:

##########################
Tutorial 06: Include Files
##########################

**********
References
**********

* Adding to `PYTHONPATH`_ with `Python sys`_ :cite:`python`
* `Python Modules`_ :cite:`python`

***********
Environment
***********

.. include:: tutorial_environment_activation.txt

.. include:: version_check_warning.txt

*******************
Directory Structure
*******************

.. include:: tutorial_directory_setup.txt

.. note::

    If you skipped any of the previous tutorials, run the following commands to create a copy of the necessary tutorial
    files.

    .. code-block:: bash

        $ pwd
        /home/roppenheimer/waves-tutorials
        $ waves fetch --overwrite --destination eabm_package tutorials/eabm_package/__init__.py
        WAVES fetch
        Destination directory: 'eabm_package'
        $ waves fetch --overwrite --destination eabm_package/abaqus 'tutorials/eabm_package/abaqus/*'
        WAVES fetch
        Destination directory: 'eabm_package/abaqus'
        $ waves fetch tutorials/tutorial_05_parameter_substitution_SConstruct && mv tutorial_05_parameter_substitution_SConstruct SConstruct
        WAVES fetch
        Destination directory: '/home/roppenheimer/waves-tutorials'

4. Download and copy the ``tutorial_05_parameter_substitution`` file to a new file named ``tutorial_06_include_files``
   with the :ref:`waves_cli` :ref:`waves_fetch_cli` subcommand.

.. code-block:: bash

   $ pwd
   /home/roppenheimer/waves-tutorials
   $ waves fetch --overwrite tutorials/tutorial_05_parameter_substitution && cp tutorial_05_parameter_substitution tutorial_06_include_files
   WAVES fetch
   Destination directory: '/home/roppenheimer/waves-tutorials'

5. Create a new directory in ``eabm_package/python`` in the ``waves-tutorials`` directory.

.. code-block:: bash

   $ pwd
   /home/roppenheimer/waves-tutorials
   $ mkdir -p eabm_package/python

.. _tutorial_include_files_waves_python_parameter_file:

*********************
Python Parameter File
*********************

In this tutorial, we will update the code from :ref:`tutorial_parameter_substitution_waves` to use an included parameter
file instead of hardcoding the parameter definitions in the ``SConscript`` file. This technique will allow parameter
re-use between simulations.

6. Create a new file ``eabm_package/python/rectangle_compression_nominal.py`` from the content below.

.. admonition:: waves-tutorials/eabm_package/python/rectangle_compression_nominal.py

   .. literalinclude:: python_rectangle_compression_nominal.py
      :language: Python

The file you just created is an exact copy of the code snippet in your ``tutorial_05_parameter_substitution``
file that defines the parameter key-value pairs.

7. Create Python module initialization files to create a project specific local Python package.

.. admonition:: waves-tutorials/eabm_package/python/__init__.py

   .. code-block::

      $ pwd
      /home/roppenheimer/waves-tutorials
      $ touch eabm_package/python/__init__.py
      $ find . -name "__init__.py"
      ./waves-tutorials/eabm_package/abaqus/__init__.py
      ./waves-tutorials/eabm_package/python/__init__.py
      ./waves-tutorials/eabm_package/__init__.py

The ``__init__.py`` files tell Python what directories to treat as a package or module. They need to exist, but do not
need any content. You can read more about `Python Modules`_ in the `Python documentation`_.

.. _tutorials_tutorial_include_files_waves:

**********
SConscript
**********

8. Use the ``diff`` below to make the following modifications to your ``tutorial_06_include_files`` file:

   * Import ``rectangle_compression_nominal`` from the ``eabm_package.python`` module
   * Remove the ``simulation_variables`` dictionary that was created in :ref:`tutorial_parameter_substitution_waves`'s
     code
   * Define ``simulation_variables``  using the newly imported ``rectangle_compression_nominal`` module

A ``diff`` against the ``SConscript`` file from :ref:`tutorial_parameter_substitution_waves` is included below to help
identify the changes made in this tutorial.

.. admonition:: waves-tutorials/tutorial_06_include_files

   .. literalinclude:: tutorials_tutorial_06_include_files
      :language: Python
      :diff: tutorials_tutorial_05_parameter_substitution

The first change to be made is importing the ``rectangle_compression_nominal`` module from the
``eabm_package.python`` module you created in the :ref:`tutorial_include_files_waves_python_parameter_file` section of
this tutorial. This import statement will import all variables within the ``rectangle_compression_nominal.py`` file
and make them available in the ``SConscript`` file's name space. See the `Python Modules`_ documentation for more
information about importing modules. You can access those variables with the following syntax:

.. code-block:: python

   rectangle_compression_nominal.simulation_variables

The second change removes the code that defines ``simulation_variables`` that remained from
:ref:`tutorial_parameter_substitution_waves`'s code.

The final change made in the ``tutorial_06_include_files`` file is to re-define the ``simulation_variables``
from the ``rectangle_compression_nominal`` module. The end result at this point in the code is the same between
this tutorial and :ref:`tutorial_parameter_substitution_waves`.  However, now we import variables from a separate file,
list that file as a source dependency of the parameterized targets, and allow ourselves the ability to change parameters
without modification to the ``SConscript`` file.

**********
SConstruct
**********

9. Use the ``diff`` below to modify your ``waves-tutorials/SConstruct`` file in the following ways:

   * Add the ``waves-tutorials`` directory to your `PYTHONPATH`_ to make the ``eabm_package`` - and thus
     the modules within it - importable
   * Add ``tutorial_06_include_files`` to the ``workflow_configurations`` list

A ``diff`` against the ``SConstruct`` file from :ref:`tutorial_parameter_substitution_waves` is included below to help identify the
changes made in this tutorial.

.. admonition:: waves-tutorials/SConstruct

   .. literalinclude:: tutorials_tutorial_06_include_files_SConstruct
      :language: Python
      :diff: tutorials_tutorial_05_parameter_substitution_SConstruct

The first change you made allows for us to import modules from the ``eabm_package`` package. This step is neccessary to
be able to import the ``eabm_package.python`` module in the ``tutorial_06_include_files`` file.

The last change to be made is adding ``tutorial_06_include_files`` to the ``workflow_configurations`` list. This
process should be quite familiar by now.

*************
Build Targets
*************

10. Build the new targets

.. code-block:: bash

    $ pwd
    /home/roppenheimer/waves-tutorials
    $ scons tutorial_06_include_files
    scons: Reading SConscript files ...
    Checking whether /apps/abaqus/Commands/abq2023 program exists.../apps/abaqus/Commands/abq2023
    Checking whether abq2023 program exists.../apps/abaqus/Commands/abq2023
    scons: done reading SConscript files.
    scons: Building targets ...
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 -information
    environment > rectangle_geometry.abaqus_v6.env
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 cae -noGui
    /home/roppenheimer/waves-tutorials/eabm_package/abaqus/rectangle_geometry.py -- --width 1.0 --height 1.0 >
    rectangle_geometry.stdout 2>&1
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 -information
    environment > rectangle_partition.abaqus_v6.env
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 cae -noGui
    /home/roppenheimer/waves-tutorials/eabm_package/abaqus/rectangle_partition.py -- --width 1.0 --height 1.0 >
    rectangle_partition.stdout 2>&1
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 -information
    environment > rectangle_mesh.abaqus_v6.env
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 cae -noGui
    /home/roppenheimer/waves-tutorials/eabm_package/abaqus/rectangle_mesh.py -- --global-seed 1.0 >
    rectangle_mesh.stdout 2>&1
    Copy("build/tutorial_06_include_files/rectangle_compression.inp.in",
    "eabm_package/abaqus/rectangle_compression.inp.in")
    Creating 'build/tutorial_06_include_files/rectangle_compression.inp'
    Copy("build/tutorial_06_include_files/assembly.inp", "eabm_package/abaqus/assembly.inp")
    Copy("build/tutorial_06_include_files/boundary.inp", "eabm_package/abaqus/boundary.inp")
    Copy("build/tutorial_06_include_files/field_output.inp", "eabm_package/abaqus/field_output.inp")
    Copy("build/tutorial_06_include_files/materials.inp", "eabm_package/abaqus/materials.inp")
    Copy("build/tutorial_06_include_files/parts.inp", "eabm_package/abaqus/parts.inp")
    Copy("build/tutorial_06_include_files/history_output.inp", "eabm_package/abaqus/history_output.inp")
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 -information
    environment > rectangle_compression.abaqus_v6.env
    cd /home/roppenheimer/waves-tutorials/build/tutorial_06_include_files && /apps/abaqus/Commands/abq2023 -job
    rectangle_compression -input rectangle_compression -double both -interactive -ask_delete no >
    rectangle_compression.stdout 2>&1
    scons: done building targets.

************
Output Files
************

Explore the contents of the ``build`` directory using the ``tree`` command against the ``build`` directory, as shown
below. Note the usage of the ``-I`` to reduce clutter in the ``tree`` command output.

.. code-block:: bash

    $ pwd
    /home/roppenheimer/waves-tutorials
    $ tree build/tutorial_06_include_files/
    build/tutorial_06_include_files/
    |-- abaqus.rpy
    |-- abaqus.rpy.1
    |-- abaqus.rpy.2
    |-- assembly.inp
    |-- boundary.inp
    |-- field_output.inp
    |-- history_output.inp
    |-- materials.inp
    |-- parts.inp
    |-- rectangle_compression.abaqus_v6.env
    |-- rectangle_compression.com
    |-- rectangle_compression.dat
    |-- rectangle_compression.inp
    |-- rectangle_compression.inp.in
    |-- rectangle_compression.msg
    |-- rectangle_compression.odb
    |-- rectangle_compression.prt
    |-- rectangle_compression.sta
    |-- rectangle_compression.stdout
    |-- rectangle_geometry.abaqus_v6.env
    |-- rectangle_geometry.cae
    |-- rectangle_geometry.jnl
    |-- rectangle_geometry.stdout
    |-- rectangle_mesh.abaqus_v6.env
    |-- rectangle_mesh.cae
    |-- rectangle_mesh.inp
    |-- rectangle_mesh.jnl
    |-- rectangle_mesh.stdout
    |-- rectangle_partition.abaqus_v6.env
    |-- rectangle_partition.cae
    |-- rectangle_partition.jnl
    `-- rectangle_partition.stdout

    0 directories, 32 files

The output files for this tutorial are *exactly* the same as those from :ref:`tutorial_parameter_substitution_waves`. As
was mentioned when modifying the :ref:`tutorials_tutorial_include_files_waves` file, the use of an included Python file
to define our parameters provides the same result as when we hard-code the parameters into the ``SConscript`` file. It
is also worth noting that the ``eabm_package/python/rectangle_compression_nominal.py`` file did not get copied to
the build directory. Instead, we added the ``eabm_package`` directory to `PYTHONPATH`_. This way we can import the
``rectangle_compression_nominal`` module from its source location and remove any need to duplicate source code by
copying files from place to place.

**********************
Workflow Visualization
**********************

View the workflow directed graph by running the following command and opening the image in your preferred image viewer.

.. code-block::

   $ pwd
   /home/roppenheimer/waves-tutorials
   $ waves visualize tutorial_06_include_files --output-file tutorial_06_include_files.png --width=28 --height=6 --exclude-list /usr/bin .stdout .jnl .env .prt .com

The output should look similar to the figure below.

.. raw:: latex

    \begin{landscape}
        \vspace*{\fill}

.. figure:: tutorial_06_include_files.png
   :align: center

.. raw:: latex

        \vspace*{\fill}
    \end{landscape}

Note that the directed graph has not grown larger than the one shown in :ref:`tutorial_parameter_substitution_waves`.
While we have added a new parameter file, the dependence is implicitly captured in the simulation variable values passed
to the subsitution dictionary. If the values in the parameter file change, the substituted
``rectangle_compression.inp`` file contents will also change. So while the parameter file is not explicitly
included in the directed graph, the contents of the ``rectangle_compression.inp`` file will still correctly prompt
re-builds when the parameter file changes.
