from __future__ import annotations

import logging
from typing import List, Sequence, Tuple, Union

import numpy as np

from ..elements import Bbox, LayoutElement

class LayoutGraph(object):
    """LayoutGraph attempts to efficiently build a modified adjacency graph over the passed elements.
    
    Each node in the graph is labelled with all 'adjacent' nodes in each of the cardinal directions, ordered by 
    edge-to-edge distance.  
    Here adjacency means that no horizontal or vertical line drawn between opposing edges of the boxes intersects
    and other box.
    
    ```
    [   a   ]    [   b   ]
    [ c ]      
    [         d          ]
    ```
    Under this diagram the adjacency relationships are (a,right,b), (a,down,c), (c,down,d), and (b,down,d) but not (a,down,d).  
    Note that adjacency is symettric, so (a,right,b) imports (b,left,a) and so on.
    """


    class Node:
        """Container for graph node, storing it's adjacent nodes and the original element
        """
        def __init__(self, id: int, element:LayoutElement):
            
            self.id = id
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
            return f"<N:{self.id} element:{el_str}>"

    def get_node(self, id_or_id_dist_pair: Union[int, Tuple[int, float]]) -> Node:
        """Retrieves a graph node from it's Id, or an (Id, distance) tuple.

        Args:
            id_or_id_dist_pair (Union[int, Tuple[int, float]]): Node Id or the (Id, distance) tuple used for storing node adjacencies

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
        if any(self.node_has_ancestor(up_adj_node_and_distance[0], target_id) \
            for up_adj_node_and_distance in anc.up):
                return True
        
        if any(self.node_has_ancestor(left_adj_node_and_distance[0], target_id) \
            for left_adj_node_and_distance in anc.left):
                return True
        
        return False

    def __get_next_overlaps_from_projection(self, node: Node, matrix_slice: np.ndarray, transpose: bool=False):

            if not transpose:
                if node.element.bbox.y1 >= self.pagebound.y1 - 1:
                    return []
                overlap_func = lambda e1, e2: e1.element.bbox.x_overlap(e2.element.bbox, 'min')
                reject_overlap_func = lambda e1: node.element.bbox.y_overlap(e1.element.bbox)
                distance_func = lambda e1, e2: max(e2.element.bbox.y0 - e1.element.bbox.y1, 0)
            else:
                if node.element.bbox.x1 >= self.pagebound.x1 - 1:
                    return []
                overlap_func = lambda e1, e2: e1.element.bbox.y_overlap(e2.element.bbox, 'min')
                reject_overlap_func = lambda e1: node.element.bbox.x_overlap(e1.element.bbox)
                distance_func = lambda e1, e2: max(e2.element.bbox.x0 - e1.element.bbox.x1, 0.)
                matrix_slice = matrix_slice.T

            #Find intersections with other nodes  
            intersects = matrix_slice[
                range(matrix_slice.shape[0]),
                 (matrix_slice != 0).argmax(axis=1)
                ]
            
            #Get distance to each intersecting node 
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
            node_distances.sort(key=lambda d: d[1] + 0.01*self.nodes[d[0]].element.bbox.y0)

            #Remove nodes which would intersect with closer ones
            none_overlapping_nodes: List[Tuple[int, float]] = []
            for distance in node_distances:
                no_overlap = True
                for d2 in none_overlapping_nodes:
                    if overlap_func(self.nodes[distance[0]], self.nodes[d2[0]]) > 0.1:
                        no_overlap = False
                        break
                if no_overlap:
                    none_overlapping_nodes.append(distance)

            return none_overlapping_nodes

    def __build_graph(self):
        matrix = np.zeros(shape=(int(self.pagebound.x1), int(self.pagebound.y1)), dtype=np.int16)

        for e in self.nodes[1:]:
            matrix[
                int(e.element.bbox.x0):int(e.element.bbox.x1),
                int(e.element.bbox.y0):int(e.element.bbox.y1)
            ] = e.id

        for e in self.nodes[1:]:
            #Get downwards elements
            matrix_slice = matrix[
                int(e.element.bbox.x0):int(e.element.bbox.x1),
                int(e.element.bbox.y1):
            ]
            e.down = self.__get_next_overlaps_from_projection(e, matrix_slice)
            
            #Get leftwards elements
            matrix_slice = matrix[
                int(e.element.bbox.x1):,
                int(e.element.bbox.y0):int(e.element.bbox.y1)
            ]
            e.right = self.__get_next_overlaps_from_projection(e, matrix_slice, True)

        for node in self.nodes[1:]:
            if len(node.up) == 0:
                node.up.append((self.root.id, node.element.bbox.y0))
                self.root.down.append((node.id, node.element.bbox.y0))

            for down_node, down_node_distance in node.down:
                self.nodes[down_node].up.append((node.id, down_node_distance))
            
            for right_node, right_node_distance in node.right:
                self.nodes[right_node].left.append((node.id, right_node_distance))

        for node in self.nodes:
            node.up.sort(key=lambda n: n[1])
            node.left.sort(key=lambda n: n[1])

        self.root.down.sort(key=lambda n:n[1])

        self.matrix = matrix



    def __init__(self, pagebound: Bbox, elements: Sequence[LayoutElement]):
        """Create a LayoutGraph from the passed elements.

        Args:
            pagebound (Bbox): Bounding box of the containing page or section
            elements (Sequence[LayoutElement]): Sequence of elements to build the layout adjacency graph
        """
        
        self.pagebound = pagebound
        self.root = LayoutGraph.Node(0, LayoutElement(Bbox(0, -2, pagebound.x1, -1, pagebound.x1, pagebound.y1)))
        self.nodes = [self.root]
        self.matrix = None
        for i,e in enumerate(elements):
            n = LayoutGraph.Node(i+1, e)
            self.nodes.append(n)

        self.__build_graph()

    def __str__(self):
        text = '='*30 + '\n'
        for n in self.nodes:
            text += "-"*30
            text += f"\n{n}"
            text += "\nU: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.up])
            text += "\nL: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.left])
            text += "\nR: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.right])
            text += "\nD: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.down])
            text += "\n"

        text += '='*30
        return text


    