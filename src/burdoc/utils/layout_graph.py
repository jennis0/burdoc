"""The LayoutGraph efficiently builds a modified adjacency graph of elements. Used by various parts of the 
processing pipeline."""

from __future__ import annotations

from typing import List, Sequence, Tuple, Union

import numpy as np

from ..elements import Bbox, LayoutElement


class LayoutGraph():
    """LayoutGraph attempts to efficiently build a modified adjacency graph over the passed elements.

    Each node in the graph is labelled with all 'adjacent' nodes in each of the cardinal directions, ordered by 
    edge-to-edge distance.  
    Here adjacency means that no horizontal or vertical line drawn between opposing edges of the boxes intersects
    and other box.

    ::
    
            [   a   ]    [   b   ]
            [ c ]      
            [         d          ]

    Under this diagram the adjacency relationships are (a,right,b), (a,down,c), (c,down,d), and 
    (b,down,d) but not (a,down,d).  
    Note that adjacency is symettric, so (a,right,b) imports (b,left,a) and so on.
    """

    class Node:
        """Container for graph node, storing it's adjacent nodes and the original element
        """

        def __init__(self, node_id: int, element: LayoutElement):

            self.node_id = node_id
            self.element = element
            self.up: List[Tuple[int, float]] = []
            """All up adjacent nodes, sorted closest to furthest
            """

            self.down: List[Tuple[int, float]] = []
            """All down adjacent nodes, sorted closest to furthest
            """

            self.left: List[Tuple[int, float]] = []
            """All left adjacent nodes, sorted closest to furthest
            """
            self.right: List[Tuple[int, float]] = []
            """All right adjacent nodes, sorted closest to furthest
            """

        def __repr__(self):
            el_str = str(self.element)
            el_str = el_str[10:min(30, len(el_str))]
            return f"<N:{self.node_id} element:{el_str}>"

    def get_node(self, id_or_id_dist_pair: Union[int, Tuple[int, float]]) -> Node:
        """Retrieves a graph node from it's Id, or an (Id, distance) tuple.

        Args:
            id_or_id_dist_pair (Union[int, Tuple[int, float]]): Node Id or the (Id, distance) tuple 
            used for storing node adjacencies

        Raises:
            IndexError: Id does not exist in the graph

        Returns:
            Node: The requested node
        """
        if isinstance(id_or_id_dist_pair, int):
            node_id = id_or_id_dist_pair
        else:
            node_id = id_or_id_dist_pair[0]

        if node_id < len(self.nodes):
            return self.nodes[node_id]
        raise IndexError()

    def node_has_ancestor(self, node_id: int, target_id: int) -> bool:
        """Check whether the target node is an 'ancestor' of the primary node.
        Here 'ancestor' means that there is a leftwards or upwards adjacency
        relations that get from the node to the target.

        Args:
            node_id (int): Starting node
            target_id (int): Node to check if in ancestry

        Returns:
            bool: Target node is ancester of starting node
        """
        if node_id == target_id:
            return True

        anc = self.nodes[node_id]
        if any(self.node_has_ancestor(up_adj_node_and_distance[0], target_id)
               for up_adj_node_and_distance in anc.up):
            return True

        if any(self.node_has_ancestor(left_adj_node_and_distance[0], target_id)
               for left_adj_node_and_distance in anc.left):
            return True

        return False

    def __get_next_overlaps_from_projection(
        self, node: Node,
        matrix_slice: np.ndarray,
        transpose: bool = False
    ):

        if not transpose:
            if node.element.bbox.y1 >= self.pagebound.y1 - 1:
                return []

            def overlap_func(element_1, element_2):
                return element_1.element.bbox.x_overlap(element_2.element.bbox, 'min')

            def reject_overlap_func(element_1):
                return node.element.bbox.y_overlap(element_1.element.bbox)

            def distance_func(element_1, element_2):
                return max(element_2.element.bbox.y0 - element_1.element.bbox.y1, 0)
        else:
            if node.element.bbox.x1 >= self.pagebound.x1 - 1:
                return []

            def overlap_func(element_1, element_2):
                return element_1.element.bbox.y_overlap(element_2.element.bbox, 'min')

            def reject_overlap_func(element_1):
                return node.element.bbox.x_overlap(element_1.element.bbox)

            def distance_func(element_1, element_2):
                return max(element_2.element.bbox.x0 - element_1.element.bbox.x1, 0.)

            matrix_slice = matrix_slice.T

        # Find intersections with other nodes
        intersects = matrix_slice[
            range(matrix_slice.shape[0]),
            (matrix_slice != 0).argmax(axis=1)
        ]

        # Get distance to each intersecting node
        node_distances: List[Tuple[int, float]] = []
        for i in np.unique(intersects):
            if i == 0:
                continue
            candidate = self.nodes[i]
            if reject_overlap_func(candidate) > 5:
                continue
            if overlap_func(node, candidate) <= 0.1:
                continue
            node_distances.append((i, distance_func(node, candidate)))
        node_distances.sort(
            key=lambda d: d[1] + 0.01*self.nodes[d[0]].element.bbox.y0)

        # Remove nodes which would intersect with closer ones
        none_overlapping_nodes: List[Tuple[int, float]] = []
        for distance in node_distances:
            no_overlap = True
            for distance2 in none_overlapping_nodes:
                if overlap_func(self.nodes[distance[0]], self.nodes[distance2[0]]) > 0.1:
                    no_overlap = False
                    break
            if no_overlap:
                none_overlapping_nodes.append(distance)

        return none_overlapping_nodes

    def __build_graph(self):
        matrix = np.zeros(shape=(int(self.pagebound.x1),
                          int(self.pagebound.y1)), dtype=np.int16)

        for node in self.nodes[1:]:
            matrix[
                int(node.element.bbox.x0):int(node.element.bbox.x1),
                int(node.element.bbox.y0):int(node.element.bbox.y1)
            ] = node.node_id

        for node in self.nodes[1:]:
            # Get downwards elements
            matrix_slice = matrix[
                int(node.element.bbox.x0):int(node.element.bbox.x1),
                int(node.element.bbox.y1):
            ]
            node.down = self.__get_next_overlaps_from_projection(
                node, matrix_slice)

            # Get leftwards elements
            matrix_slice = matrix[
                int(node.element.bbox.x1):,
                int(node.element.bbox.y0):int(node.element.bbox.y1)
            ]
            node.right = self.__get_next_overlaps_from_projection(
                node, matrix_slice, True)

        for node in self.nodes[1:]:
            if len(node.up) == 0:
                node.up.append((self.root.node_id, node.element.bbox.y0))
                self.root.down.append((node.node_id, node.element.bbox.y0))

            for down_node, down_node_distance in node.down:
                self.nodes[down_node].up.append(
                    (node.node_id, down_node_distance))

            for right_node, right_node_distance in node.right:
                self.nodes[right_node].left.append(
                    (node.node_id, right_node_distance))

        for node in self.nodes:
            node.up.sort(key=lambda n: n[1])
            node.left.sort(key=lambda n: n[1])

        self.root.down.sort(key=lambda n: n[1])

        self.matrix = matrix

    def __init__(self, pagebound: Bbox, elements: Sequence[LayoutElement]):
        """Create a LayoutGraph from the passed elements.

        Args:
            pagebound (Bbox): Bounding box of the containing page or section
            elements (Sequence[LayoutElement]): Sequence of elements to build the layout adjacency graph
        """

        self.pagebound = pagebound
        self.root = LayoutGraph.Node(0, LayoutElement(
            Bbox(0, -2, pagebound.x1, -1, pagebound.x1, pagebound.y1)))
        self.nodes = [self.root]
        self.matrix = None
        for i, element in enumerate(elements):
            self.nodes.append(LayoutGraph.Node(i+1, element))

        self.__build_graph()

    def __str__(self):
        text = '='*30 + '\n'
        for node in self.nodes:
            text += "-"*30
            text += f"\n{node}"
            text += "\nU: " + \
                ',\n   '.join(
                    ['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in node.up])
            text += "\nL: " + \
                ',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' +
                              str(round(n2[1], 1)) + ')' for n2 in node.left])
            text += "\nR: " + \
                ',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' +
                              str(round(n2[1], 1)) + ')' for n2 in node.right])
            text += "\nD: " + \
                ',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' +
                              str(round(n2[1], 1)) + ')' for n2 in node.down])
            text += "\n"

        text += '='*30
        return text
