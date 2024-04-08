"""Internal API module implementing the ``visualize`` subcommand behavior.

Should raise ``RuntimeError`` or a derived class of :class:`waves.exceptions.WAVESError` to allow the CLI implementation
to convert stack-trace/exceptions into STDERR message and non-zero exit codes.
"""
import pathlib
import sys
import re

import networkx
import matplotlib.pyplot as plt

from waves import _settings


_exclude_from_namespace = set(globals().keys())


def get_parser():
    pass


def parse_output(tree_lines: list, exclude_list: list, exclude_regex: str) -> dict:
    """
    Parse the string that has the tree output and store it in a dictionary

    :param tree_lines: output of the scons tree command
    :param exclude_list: exclude nodes starting with strings in this list(e.g. /usr/bin)
    :param exclude_regex: exclude nodes that match this regular expression

    :returns: dictionary of tree output
    """
    edges = list()  # List of tuples for storing all connections
    node_info = dict()
    node_number = 0
    nodes = list()
    higher_nodes = dict()
    graphml_nodes = ''
    graphml_edges = ''
    exclude_node = False
    exclude_indent = 0
    for line in tree_lines:
        line_match = re.match(r'^\[(.*)\](.*)\+-(.*)', line)
        if line_match:
            status = [_settings._scons_tree_status[_] for _ in line_match.group(1) if _.strip()]
            placement = line_match.group(2)
            node_name = line_match.group(3)
            current_indent = int(len(placement) / 2) + 1
            if current_indent <= exclude_indent and exclude_node:
                exclude_node = False
            if exclude_node:
                continue
            for exclude in exclude_list:
                if node_name.startswith(exclude) or node_name.endswith(exclude):
                    exclude_node = True
                    exclude_indent = current_indent
            exclude_node, exclude_indent = check_regex_exclude(exclude_regex, node_name, current_indent,
                                                               exclude_indent, exclude_node)
            if exclude_node:
                continue
            node_number += 1  # Increment the node_number
            if node_name not in nodes:
                nodes.append(node_name)
                graphml_nodes += f'    <node id="{node_name}"><data key="label">{node_name}</data></node>\n'
                node_info[node_name] = dict()
            higher_nodes[current_indent] = node_name

            if current_indent != 1:  # If it's not the first node which is the top level node
                higher_node = higher_nodes[current_indent - 1]
                edges.append((higher_node, node_name))
                graphml_edges += f'    <edge source="{higher_node}" target="{node_name}"/>\n'
            node_info[node_name]['status'] = status

    tree_dict = dict()
    tree_dict['nodes'] = nodes
    tree_dict['edges'] = edges
    tree_dict['node_info'] = node_info

    tree_dict['graphml'] = '''<?xml version = "1.0" encoding = "UTF-8"?>
      <graphml xmlns="http://graphml.graphdrawing.org/xmlns"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
      http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd ">
      <graph id = "tree" edgedefault = "directed">
    '''
    tree_dict['graphml'] += graphml_nodes
    tree_dict['graphml'] += graphml_edges
    tree_dict['graphml'] += '  </graph>\n</graphml>\n'

    return tree_dict


def check_regex_exclude(exclude_regex: str, node_name: str, current_indent: int, exclude_indent: int,
                        exclude_node: bool = False) -> tuple[bool, int]:
    """
    Excludes node names that match the regular expression

    :param str exclude_regex: Regular expression
    :param str node_name: Name of the node
    :param int current_indent: Current indent of the parsed output
    :param int exclude_indent: Set to current_indent if node is to be excluded
    :param bool exclude_node: Indicated whether a node should be excluded

    :returns: Tuple containing exclude_node and exclude_indent
    """
    if exclude_regex and re.search(exclude_regex, node_name):
        exclude_node = True
        exclude_indent = current_indent
    return exclude_node, exclude_indent


def click_arrow(event, annotations: dict, arrows: dict) -> None:
    """
    Create effect with arrows when mouse click

    :param matplotlib.backend_bases.Event event: Event that is handled by this function
    :param annotations: Dictionary linking node names to their annotations
    :param arrows: Dictionary linking darker arrow annotations to node names
    """
    fig = plt.gcf()
    ax = plt.gca()
    for key in annotations.keys():
        if annotations[key].contains(event)[0]:  # If the text annotation contains the event (i.e. is clicked on)
            for to_arrow in arrows[key]['to']:
                if to_arrow:
                    if to_arrow.get_visible():
                        to_arrow.set_visible(False)
                    else:
                        to_arrow.set_visible(True)
                    fig.canvas.draw_idle()
            for from_arrow in arrows[key]['from']:
                if from_arrow:
                    if from_arrow.get_visible():
                        from_arrow.set_visible(False)
                    else:
                        from_arrow.set_visible(True)
                    fig.canvas.draw_idle()


def visualize(tree: dict, output_file: str,
              height: int = _settings._visualize_default_height,
              width: int = _settings._visualize_default_width,
              font_size: int = _settings._visualize_default_font_size,
              vertical: bool = False, no_labels: bool = False) -> None:
    """Create a visualization showing the tree

    :param tree: output of the scons tree command stored as dictionary
    :param output_file: Name of file to store visualization
    :param height: Height of visualization if being saved to a file
    :param width: Width of visualization if being saved to a file
    :param font_size: Font size of file names in points
    :param vertical: Specifies a vertical layout of graph instead of the default horizontal layout
    :param no_labels: Don't print labels on the nodes of the visualization
    """
    graph = networkx.DiGraph()
    graph.add_nodes_from(tree['nodes'])
    graph.add_edges_from(tree['edges'])

    for layer, nodes in enumerate(networkx.topological_generations(graph)):
        # `multipartite_layout` expects the layer as a node attribute, so it's added here
        for node in nodes:
            graph.nodes[node]["layer"] = layer
    if vertical:
        pos = networkx.multipartite_layout(graph, subset_key="layer", align="horizontal")
        for k in pos:  # Flip the layout so the root node is on top
            pos[k][-1] *= -1
    else:
        pos = networkx.multipartite_layout(graph, subset_key="layer")
    networkx.draw_networkx_nodes(graph, pos=pos, node_size=0)  # The nodes are drawn tiny so that labels can go on top

    box_color = '#5AC7CB'  # Light blue from Waves Logo
    arrow_color = '#B7DEBE'  # Light green from Waves Logo
    # TODO: separate plot construction from output for easier unit testing
    annotations = dict()
    arrows = dict()
    ax = plt.gca()
    ax.axis('off')
    fig = plt.gcf()
    for A, B in graph.edges:  # Arrows and labels are written on top of existing nodes, which are laid out by networkx
        label_A = A
        label_B = B
        if no_labels:
            label_A = " "
            label_B = " "
        patchA = ax.annotate(label_A, xy=pos[A], xycoords='data', ha='center', va='center', size=font_size,
                             bbox=dict(facecolor=box_color, boxstyle='round'))
        patchB = ax.annotate(label_B, xy=pos[B], xycoords='data', ha='center', va='center', size=font_size,
                             bbox=dict(facecolor=box_color, boxstyle='round'))
        arrowprops = dict(
            arrowstyle="<-", color=arrow_color, connectionstyle='arc3,rad=0.1', patchA=patchA, patchB=patchB)
        ax.annotate("", xy=pos[B], xycoords='data', xytext=pos[A], textcoords='data', arrowprops=arrowprops)

        annotations[A] = patchA
        annotations[B] = patchB
        dark_props = dict(arrowstyle="<-", color="0.0", connectionstyle='arc3,rad=0.1', patchA=patchA, patchB=patchB)
        dark_arrow = ax.annotate("", xy=pos[B], xycoords='data', xytext=pos[A], textcoords='data',
                                 arrowprops=dark_props)
        dark_arrow.set_visible(False)  # Draw simultaneous darker arrow, but don't show it
        try:
            arrows[A]['from'].append(dark_arrow)
        except KeyError:
            arrows[A] = dict()
            arrows[A]['from'] = list()
            arrows[A]['to'] = list()
            arrows[A]['from'].append(dark_arrow)
        try:
            arrows[B]['to'].append(dark_arrow)
        except KeyError:
            arrows[B] = dict()
            arrows[B]['from'] = list()
            arrows[B]['to'] = list()
            arrows[B]['to'].append(dark_arrow)

    fig.canvas.mpl_connect("button_press_event", lambda x: click_arrow(x, annotations, arrows))

    if output_file:
        file_name = pathlib.Path(output_file)
        file_name.parent.mkdir(parents=True, exist_ok=True)
        suffix = file_name.suffix
        if not suffix or suffix[1:] not in list(fig.canvas.get_supported_filetypes().keys()):
            # If there is no suffix or it's not supported by matplotlib, use svg
            file_name = file_name.with_suffix('.svg')
            print(f"WARNING: extension '{suffix}' is not supported by matplotlib. Falling back to '{file_name}'",
                  file=sys.stderr)
        fig = plt.gcf()
        fig.set_size_inches((width, height), forward=False)
        fig.savefig(str(file_name))
    else:
        plt.show()
    plt.clf()  # Indicates that we are done with the plot


# Limit help() and 'from module import *' behavior to the module's public API
_module_objects = set(globals().keys()) - _exclude_from_namespace
__all__ = [name for name in _module_objects if not name.startswith("_")]
