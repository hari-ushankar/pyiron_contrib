from __future__ import print_function
# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pyiron_contrib.protocol.utils import LoggerMixin
from pyiron_contrib.protocol.io import Input, Output
from abc import ABC, abstractmethod

"""
The goal here is to abstract and simplify the graph functionality.
"""


__author__ = "Liam Huber, Dominik Gehringer"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "Feb 10, 2020"


class Vertex(LoggerMixin, ABC):
    DEFAULT_STATE = "next"

    def __init__(self, *args, vertex_name=None, **kwargs):
        super(Vertex, self).__init__()

        self.input = Input()
        self.output = Output()
        self.init_io_channels()
        self.clock = 0
        self.vertex_name = vertex_name
        self._vertex_state = self.DEFAULT_STATE
        self.possible_vertex_states = [self.DEFAULT_STATE]

    @property
    def vertex_state(self):
        return self._vertex_state

    @vertex_state.setter
    def vertex_state(self, new_state):
        if new_state not in self.possible_vertex_states:
            raise ValueError("New state not in list of possible states")
        self._vertex_state = new_state

    @abstractmethod
    def init_io_channels(self):
        """Define channels for vertex input and output."""
        pass

    def execute(self):
        """Just parse the input and do your physics, then store the output."""
        print("{} unresolved input = {}\n resolved input = {}".format(self.vertex_name, self.input, self.input.resolve()))
        output_data = self.function(**self.input.resolve())
        self.update_and_archive(output_data)

    @abstractmethod
    def function(self, *args, **kwargs):
        """
        The vertex-specific logic to be executed.

        Args:
            Must have one arg/kwarg variable for each input channel with the same name.

        Returns:
            (dict): With items matching output channels (or empty dict if no output).
        """
        pass

    def update_and_archive(self, output_data):
        print("Updating {}".format(self.vertex_name))
        for key, value in output_data.items():
            getattr(self.output, key).push(value)

        self._update_archive()

    def _update_archive(self):
        pass


class Graph(Vertex):
    def __init__(self):
        super(Graph, self).__init__()

        self.vertices = Vertices()
        self.edges = Edges()
        self.starting_vertex = None
        self.restarting_vertex = None

        # Set up the graph
        self.set_vertices()
        self._initialize_edges()
        self.set_edges()
        self.wire_data_flow()
        if self.starting_vertex is None:
            self.logger.warn("Starting vertex not set for {}".format(self.vertex_name))

        # On initialization, set the active vertex to starting vertex
        self.active_vertex = self.starting_vertex

    @abstractmethod
    def set_vertices(self):
        """Add child vertices to the graph."""
        pass

    def _initialize_edges(self):
        for v in self.vertices.values():
            self.edges.initialize(v)

    @abstractmethod
    def set_edges(self):
        """Wire the logic for traversing the graph edges."""
        pass

    @abstractmethod
    def wire_data_flow(self):
        """Connect input and output information inside the graph. Also set the archive clock for all vertices."""
        pass

    def function(self, *args, **kwargs):
        while self.active_vertex is not None:
            self.active_vertex.execute()
            self.step()
        output_data = self.get_output()
        return output_data

    def step(self):
        """
        Follows the edge out of the active vertex to get the name of the next vertex and set it as the active vertex.
        If the active vertex has multiple possible states, the outbound edge for the current state will be chosen.
        """
        vertex = self.active_vertex
        if vertex is not None:
            next_vertex_name = self.edges[vertex.vertex_name][vertex.vertex_state]

            if next_vertex_name is None:
                self.active_vertex = None
            else:
                self.active_vertex = self.vertices[next_vertex_name]

    @abstractmethod
    def get_output(self):
        """Collect (and possibly rename) data from child vertices and return as a dict matching output channels."""
        pass

    def reset(self):
        if self.active_vertex is not None:
            raise ValueError("Tried to restart {}, but graph was at {} instead of None".format(
                self.vertex_name, self.active_vertex.vertex_name))

        if self.restarting_vertex is None:
            self.logger.warn("Reseting graph {} but found no restarting vertex.".format(self.vertex_name))

        self.active_vertex = self.restarting_vertex

    def __getattr__(self, item):
        return getattr(self.vertices, item)


class DotDict(dict):
    """A dictionary which allows `.` setting and getting for items."""

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __getattr__(self, item):
        return self.__getitem__(item)


class Vertices(DotDict):
    """
    Stores vertices and synchronizes their `vertex_name` attribute with the key to keep graph, vertices, and edges all
    synchonized.
    """

    def __init__(self):
        pass

    def __setitem__(self, key, value):
        if not isinstance(value, Vertex):
            raise TypeError("Vertices can only contain Vertex objects but got {}".format(type(value)))
        value.vertex_name = key
        super(Vertices, self).__setitem__(key, value)


class Edges(DotDict):
    """
    A nested dictionary of names specifying vertices, their states, and which vertex to go to next when leaving with
    a given state.
    """

    def __init__(self):
        pass

    def __setitem__(self, key, value):
        """Set vertex as a dead end -- all states lead to `None`."""

        if not isinstance(value, Vertex):
            raise TypeError("Edges can only be established for Vertex objects but got {}".format(type(value)))
        if key != value.vertex_name:
            raise ValueError("Edge dictionaries must have the same name as the vertex they are for. Expected {}"
                             "but got {}".format(value.vertex_name, key))
        super(Edges, self).__setitem__(key, DotDict({k: None for k in value.possible_vertex_states}))

    def initialize(self, vertex):
        self.__setitem__(vertex.vertex_name, vertex)

    def set_flow_chain(self, *args):
        """
        Create a chain of edges by specifying a series of vertices. If two consecutive vertices are provided, the edge
        runs along the first vertex's default state. Alternatively, the state to make the edge for can be explicitly
        specified by putting the appropriate string between two vertices in the arguments.

        Args:
            *args (Vertex/str): Vertex objects or a possible state of the previous argument.
        """

        for n, vertex in enumerate(args[:-1]):
            if not isinstance(vertex, Vertex):
                continue

            next_obj = args[n + 1]
            if isinstance(next_obj, str):
                state = next_obj
                next_vertex = args[n + 2]
            else:
                state = Vertex.DEFAULT_STATE
                next_vertex = args[n + 1]

            if not (isinstance(vertex, Vertex) and isinstance(next_vertex, Vertex)):
                raise TypeError("Edge flow must be between Vertex objects, but got {} and {}".format(
                    type(vertex), type(next_vertex)
                ))

            if state not in vertex.possible_vertex_states:
                raise KeyError("Got state {} which is not in {} for vertex {}".format(
                    state, vertex.possible_vertex_states, vertex.vertex_name
                ))

            self[vertex.vertex_name][state] = next_vertex.vertex_name