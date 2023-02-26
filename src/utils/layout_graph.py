from __future__ import annotations
from typing import List
from uuid import uuid4

from ..elements.element import LayoutElement
from ..elements.bbox import Bbox
import numpy as np
import logging
from timeit import timeit


class LayoutGraph(object):


    class Node:
        def __init__(self, id: int, element: LayoutElement):
            self.id = id
            self.element = element
            self.up = []
            self.down = []
            self.left = []
            self.right = []

        def __repr__(self):
            el_str = str(self.element)
            el_str = el_str[10:min(30, len(el_str))]
            return f"<N:{self.id} element:{el_str}>"

    def get_node(self, id_dist_pair) -> Node:
        if id_dist_pair[0] < len(self.nodes):
            return self.nodes[id_dist_pair[0]]


    def node_has_ancester(self, node_id: int, target_id: int):
        if node_id == target_id:
            return True

        anc = self.nodes[node_id]
        for a in anc.up:
            if self.node_has_ancester(a[0], target_id):
                return True
        
        for a in anc.left:
            if self.node_has_ancester(a[0], target_id):
                return True
        
        return False

    def __get_next_overlaps_from_projection(self, node: Node, slice: np.array, transpose: bool=False):

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
                distance_func = lambda e1, e2: max(e2.element.bbox.x0 - e1.element.bbox.x1, 0)
                slice = slice.T

            #Find intersections with other nodes  
            intersects = slice[
                range(slice.shape[0]),
                 (slice != 0).argmax(axis=1)
                ]
            
            #Get distance to each intersecting node 
            node_distances = []
            for i in np.unique(intersects):
                if i == 0:
                    continue
                candidate = self.nodes[i]
                if reject_overlap_func(candidate) > 5:
                    continue
                if overlap_func(node, candidate) <= 0.1:
                    continue    
                node_distances.append([i, distance_func(node, candidate)])
            node_distances.sort(key=lambda d: d[1] + 0.01*self.nodes[d[0]].element.bbox.y0)

            #Remove nodes which would intersect with closer ones
            non_overlapping_nodes = []
            for d in node_distances:
                no_overlap = True
                for d2 in non_overlapping_nodes:
                    if overlap_func(self.nodes[d[0]], self.nodes[d2[0]]) > 0.1:
                        no_overlap = False
                        break
                if no_overlap:
                    non_overlapping_nodes.append(d)

            return non_overlapping_nodes

    def __build_graph(self):
        matrix = np.zeros(shape=(int(self.pagebound.x1), int(self.pagebound.y1)), dtype=np.int16)

        for e in self.nodes[1:]:
            matrix[
                int(e.element.bbox.x0):int(e.element.bbox.x1),
                int(e.element.bbox.y0):int(e.element.bbox.y1)
            ] = e.id

        for e in self.nodes[1:]:
            #Get downwards elements
            slice = matrix[
                int(e.element.bbox.x0):int(e.element.bbox.x1),
                int(e.element.bbox.y1):
            ]
            e.down = self.__get_next_overlaps_from_projection(e, slice)
            
            #Get leftwards elements
            slice = matrix[
                int(e.element.bbox.x1):,
                int(e.element.bbox.y0):int(e.element.bbox.y1)
            ]
            e.right = self.__get_next_overlaps_from_projection(e, slice, True)

        for node in self.nodes[1:]:
            if len(node.up) == 0:
                node.up.append([self.root.id, node.element.bbox.y0])
                self.root.down.append((node.id, node.element.bbox.y0))

            for n,d in node.down:
                self.nodes[n].up.append([node.id, d])
            
            for n,d in node.right:
                self.nodes[n].left.append([node.id, d])

        for node in self.nodes:
            node.up.sort(key=lambda n: n[1])
            node.left.sort(key=lambda n: n[1])

        self.root.down.sort(key=lambda n:n[1])



    def __init__(self, logger: logging.Logger, pagebound: Bbox, elements: List[LayoutElement]):
        self.logger = logger.getChild('layoutgraph')
        self.pagebound = pagebound
        self.root = LayoutGraph.Node(0, LayoutElement(Bbox(0, -2, pagebound.x1, -1, pagebound.x1, pagebound.y1)))
        self.nodes = [self.root]
        for i,e in enumerate(elements):
            n = LayoutGraph.Node(i+1, e)
            self.nodes.append(n)

        self.__build_graph()

    def __str__(self):
        text = '"'*30
        for n in self.nodes:
            text += "'"*30
            text += f"\n{n}"
            text += "\nU: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.up])
            text += f"\nL: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.left])
            text += f"\nR: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.right])
            text += f"\nD: " +',\n   '.join(['(' + str(self.nodes[n2[0]]) + ',' + str(round(n2[1], 1)) + ')' for n2 in n.down])
            text += "\n" + "'"*30

        text += '"'*30
        return text


    