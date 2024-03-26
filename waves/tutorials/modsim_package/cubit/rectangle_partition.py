import sys
import argparse
import pathlib
import shutil

import cubit


def main(input_file, output_file, width, height):
    """Partition the simple rectangle geometry created by ``rectangle_geometry.py``

    This script partitions a simple Cubit model with a single rectangle part.

    **Element sets:**

    * ``top`` - top edge
    * ``bottom`` - bottom edge
    * ``left`` - left edge
    * ``right`` - right edge

    :param str input_file: The Cubit model file created by ``rectangle_geometry.py`` without extension. Will be
        appended with the required extension, e.g. ``input_file``.cub
    :param str output_file: The output file for the Cubit model without extension. Will be appended with the required
        extension, e.g. ``output_file``.cub
    :param float width: The rectangle width
    :param float height: The rectangle height

    :returns: writes ``output_file``.cub
    """

    input_with_extension = f"{input_file}.cub"
    output_with_extension = f"{output_file}.cub"

    # Avoid modifying the contents or timestamp on the input file.
    # Required to get conditional re-builds with a build system such as GNU Make, CMake, or SCons
    if input_file != output_file:
        shutil.copyfile(input_with_extension, output_with_extension)

    cubit.init(['cubit', '-noecho', '-nojournal', '-nographics', '-batch'])
    cubit.cmd('new')
    cubit.cmd('reset')

    cubit.cmd(f"open '{output_with_extension}'")

    cubit.cmd("sideset 1 add curve 3")
    cubit.cmd("sideset 1 name 'elset_top'")
    cubit.cmd("sideset 2 add curve 1")
    cubit.cmd("sideset 2 name 'elset_bottom'")
    cubit.cmd("sideset 3 add curve 4")
    cubit.cmd("sideset 3 name 'elset_left'")
    cubit.cmd("sideset 4 add curve 2")
    cubit.cmd("sideset 4 name 'elset_right'")

    cubit.cmd(f"save as '{output_with_extension}' overwrite")


def get_parser():
    script_name = pathlib.Path(__file__)
    # Set default parameter values
    default_input_file = script_name.stem.replace('_partition', '_geometry')
    default_output_file = script_name.stem
    default_width = 1.0
    default_height = 1.0

    prog = f"python {script_name.name} "
    cli_description = "Partition the simple rectangle geometry created by ``rectangle_geometry.py`` " \
                      "and write an ``output_file``.cub Cubit model file."
    parser = argparse.ArgumentParser(description=cli_description,
                                     prog=prog)
    parser.add_argument('--input-file', type=str, default=default_input_file,
                        help="The Cubit model file created by ``rectangle_geometry.py`` without extension. " \
                             "Will be appended with the required extension, e.g. ``input_file``.cub")
    parser.add_argument('--output-file', type=str, default=default_output_file,
                        help="The output file for the Cubit model without extension. Will be appended with the " \
                             "required extension, e.g. ``output_file``.cub")
    parser.add_argument('--width', type=float, default=default_width,
                        help="The rectangle width")
    parser.add_argument('--height', type=float, default=default_height,
                        help="The rectangle height")
    return parser


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()
    sys.exit(main(input_file=args.input_file,
                  output_file=args.output_file,
                  width=args.width,
                  height=args.height))
