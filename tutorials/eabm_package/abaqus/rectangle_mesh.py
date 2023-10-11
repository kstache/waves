import sys
import os
import argparse
import inspect
import shutil

import abaqus
import abaqusConstants
import mesh

# Import the shared abaqus utilities, trying both tutorial directory structures.
# Most end-users will implement only one of these structures and should replace
# the try/except structure with a single import line, e.g.
#
# import eabm_package.abaqus.abaqus_journal_utilities as abaqus_journal_utilities
try:
    import eabm_package.abaqus.abaqus_journal_utilities as abaqus_journal_utilities
except ImportError:
    import abaqus_journal_utilities


def main(input_file, output_file, model_name, part_name, global_seed):
    """Mesh the simple rectangle geometry partitioned by ``rectangle_partition.py``

    This script meshes a simple Abaqus model with a single rectangle part.

    **Node sets:**

    * ``ALLNODES`` - all part nodes

    **Element sets:**

    * ``ELEMENTS`` - all part elements

    :param str input_file: The Abaqus model file created by ``rectangle_geometry.py`` without extension. Will be
        appended with the required extension, e.g. ``input_file``.cae
    :param str output_file: The output file for the Abaqus model without extension. Will be appended with the required
        extension, e.g. ``output_file``.cae
    :param str model_name: The name of the Abaqus model
    :param str part_name: The name of the Abaqus part
    :param float global_seed: The global mesh seed size

    :returns: ``output_file``.cae, ``output_file``.inp
    """

    input_with_extension = '{}.cae'.format(input_file)
    output_with_extension = '{}.cae'.format(output_file)

    # Avoid modifying the contents or timestamp on the input file.
    # Required to get conditional re-builds with a build system such as GNU Make, CMake, or SCons
    if input_file != output_file:
        shutil.copyfile(input_with_extension, output_with_extension)

    abaqus.openMdb(pathName=output_with_extension)

    p = abaqus.mdb.models[model_name].parts[part_name]
    a = abaqus.mdb.models[model_name].rootAssembly
    a.Instance(name=part_name, part=p, dependent=abaqusConstants.ON)

    p.seedPart(size=global_seed, deviationFactor=0.1, minSizeFactor=0.1)
    p.generateMesh()

    elemType1 = mesh.ElemType(elemCode=abaqusConstants.CPS4R, elemLibrary=abaqusConstants.STANDARD)

    f = p.faces
    s = p.edges
    faces = f[:]

    pickedRegions = (faces, )

    p.setElementType(regions=pickedRegions, elemTypes=(elemType1,))
    p.Set(faces=faces, name='ELEMENTS')
    p.Set(faces=faces, name='ALLNODES')

    model_object = abaqus.mdb.models[model_name]
    abaqus_journal_utilities.export_mesh(model_object, part_name, output_file)

    abaqus.mdb.save()

    return 0


def get_parser():
    # The global '__file__' variable doesn't appear to be set when executing from Abaqus CAE
    filename = inspect.getfile(lambda: None)
    basename = os.path.basename(filename)
    basename_without_extension, extension = os.path.splitext(basename)
    # Construct a part name from the filename less the workflow step
    default_part_name = basename_without_extension
    suffix = '_mesh'
    if default_part_name.endswith(suffix):
        default_part_name = default_part_name[:-len(suffix)]
    # Set default parameter values
    default_input_file = '{}_partition'.format(default_part_name)
    default_output_file = '{}'.format(basename_without_extension)
    default_global_seed = 1.0

    prog = "abaqus cae -noGui {} --".format(basename)
    cli_description = "Mesh the simple rectangle geometry partitioned by ``rectangle_partition.py`` " \
                      "and write an ``output_file``.cae Abaqus model file and ``output_file``.inp orphan mesh file."
    parser = argparse.ArgumentParser(description=cli_description,
                                     prog=prog)
    parser.add_argument('--input-file', type=str, default=default_input_file,
                        help="The Abaqus model file created by ``rectangle_geometry.py`` without extension. " \
                             "Will be appended with the required extension, e.g. ``input_file``.cae")
    parser.add_argument('--output-file', type=str, default=default_output_file,
                        help="The output file for the Abaqus model without extension. Will be appended with the " \
                             "required extension, e.g. ``output_file``.cae")
    parser.add_argument('--model-name', type=str, default=default_part_name,
                        help="The name of the Abaqus model")
    parser.add_argument('--part-name', type=str, default=default_part_name,
                        help="The name of the Abaqus part")
    parser.add_argument('--global-seed', type=float, default=default_global_seed,
                        help="The global mesh seed size")
    return parser


if __name__ == '__main__':
    parser = get_parser()
    # Abaqus does not strip the CAE options, so we have to skip the unknown options related to the CAE CLI.
    args, unknown = parser.parse_known_args()
    sys.exit(main(input_file=args.input_file,
                  output_file=args.output_file,
                  model_name=args.model_name,
                  part_name=args.part_name,
                  global_seed=args.global_seed))
