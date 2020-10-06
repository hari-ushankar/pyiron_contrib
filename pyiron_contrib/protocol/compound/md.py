# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from __future__ import print_function

from abc import ABC

from pyiron_contrib.protocol.generic import CompoundVertex, Protocol
from pyiron_contrib.protocol.primitive.one_state import Counter, ExternalHamiltonian, RandomVelocity, Zeros, \
    VerletPositionUpdate, VerletVelocityUpdate, WelfordOnline, \
    HarmonicHamiltonian, BerendsenBarostat
from pyiron_contrib.protocol.primitive.two_state import IsGEq, ModIsZero
from pyiron_contrib.protocol.primitive.fts_vertices import PositionsRunningAverage
from pyiron_contrib.protocol.utils import Pointer

"""
Protocol for molecular dynamics.
"""

__author__ = "Liam Huber"
__copyright__ = "Copyright 2019, Max-Planck-Institut für Eisenforschung GmbH " \
                "- Computational Materials Design (CM) Department"
__version__ = "0.0"
__maintainer__ = "Liam Huber"
__email__ = "huber@mpie.de"
__status__ = "development"
__date__ = "18 July, 2019"


class MolecularDynamics(CompoundVertex):
    """
    Runs molecular dynamics. This isn't particularly useful as almost every source code/plain job can do this on its
    own, but rather this is intended for testing and teaching. It also serves as a useful starting point for developing
    algorithms with modified dynamics.

    Input attributes:
        ref_job_full_path (str): Path to the pyiron job to use for evaluating forces and energies.
        structure (Atoms): The structure evolve.
        temperature (float): Temperature to run at in K.
        n_steps (int): How many MD steps to run for. (Default is 100.)
        temperature_damping_timescale (float): Langevin thermostat timescale in fs. (Default is None, which runs NVE.)
        time_step (float): MD time step in fs. (Default is 1.)

    Output attributes:
        energy_pot (float): Total potential energy of the system in eV.
        energy_kin (float): Total kinetic energy of the system in eV.
        positions (numpy.ndarray): Atomic positions in angstroms.
        velocities (numpy.ndarray): Atomic velocities in angstroms/fs.
        forces (numpy.ndarray): Atomic forces in eV/angstrom. Note: These are the potential gradient forces; thermostat
            forces (if any) are not saved.
    """

    DefaultWhitelist = {
        'verlet_positions': {
            'output': {
                'positions': 1000,
            },
        },
        'calc_static': {
            'output': {
                'energy_pot': 1,
                'forces': 1000,
            },
        },
        'verlet_velocities': {
            'output': {
                'energy_kin': 1,
                'velocities': 1000,
            },
        },
    }

    def __init__(self, **kwargs):
        super(MolecularDynamics, self).__init__(**kwargs)

        # Protocol defaults
        id_ = self.input.default
        id_.temperature = None
        id_.pressure = None
        id_.style = 'anisotropic'
        id_.previous_volume = None
        id_.energy_kin = None
        id_.n_steps = 100
        id_.time_step = 1.
        id_.temperature_damping_timescale = 100.
        id_.overheat_fraction = 2
        id_.pressure_damping_timescale = 1000.
        id_.compressibility = 4.57e-5  # bar^-1

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.initial_velocities = RandomVelocity()
        g.initial_forces = Zeros()
        g.initial_pressures = Zeros()
        g.check_steps = IsGEq()
        g.clock = Counter()
        g.barostat = BerendsenBarostat()
        g.verlet_positions = VerletPositionUpdate()
        g.calc_static = ExternalHamiltonian()
        g.verlet_velocities = VerletVelocityUpdate()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.initial_velocities,
            g.initial_forces,
            g.initial_pressures,
            g.check_steps, 'false',
            g.barostat,
            g.verlet_positions,
            g.calc_static,
            g.verlet_velocities,
            g.clock,
            g.check_steps
        )
        g.starting_vertex = g.initial_velocities
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # initial_velocity
        g.initial_velocities.input.temperature = ip.temperature
        g.initial_velocities.input.masses = ip.structure.get_masses
        g.initial_velocities.input.overheat_fraction = ip.overheat_fraction

        # initial_forces
        g.initial_forces.input.shape = ip.structure.positions.shape

        # initial_pressures
        g.initial_pressures.input.shape = ip.structure.cell.shape

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # barostat
        g.barostat.input.default.box_pressure = gp.initial_pressures.output.zeros[-1]
        g.barostat.input.default.structure = ip.structure
        g.barostat.input.default.energy_kin = ip.energy_kin
        g.barostat.input.default.previous_volume = ip.previous_volume
        g.barostat.input.default.positions = ip.structure.positions

        g.barostat.input.box_pressure = gp.calc_static.output.pressures[-1]
        g.barostat.input.structure = gp.barostat.output.structure[-1]
        g.barostat.input.energy_kin = gp.verlet_velocities.output.energy_kin[-1]
        g.barostat.input.previous_volume = gp.calc_static.output.volume[-1]
        g.barostat.input.positions = gp.verlet_positions.output.positions[-1]

        g.barostat.input.pressure = ip.pressure
        g.barostat.input.temperature = ip.temperature
        g.barostat.input.time_step = ip.time_step
        g.barostat.input.pressure_damping_timescale = ip.pressure_damping_timescale
        g.barostat.input.compressibility = ip.compressibility
        g.barostat.input.style = ip.style

        # verelt_positions
        g.verlet_positions.input.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.verlet_positions.input.default.forces = gp.initial_forces.output.zeros[-1]

        g.verlet_positions.input.positions = gp.barostat.output.positions[-1]
        g.verlet_positions.input.velocities = gp.verlet_velocities.output.velocities[-1]
        g.verlet_positions.input.forces = gp.calc_static.output.forces[-1]

        g.verlet_positions.input.masses = ip.structure.get_masses
        g.verlet_positions.input.time_step = ip.time_step
        g.verlet_positions.input.temperature = ip.temperature
        g.verlet_positions.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # calc_static
        g.calc_static.input.ref_job_full_path = ip.ref_job_full_path
        g.calc_static.input.structure = gp.barostat.output.structure[-1]
        g.calc_static.input.cell = gp.barostat.output.structure[-1].cell
        g.calc_static.input.positions = gp.verlet_positions.output.positions[-1]

        # verlet_velocities
        g.verlet_velocities.input.velocities = gp.verlet_positions.output.velocities[-1]
        g.verlet_velocities.input.forces = gp.calc_static.output.forces[-1]

        g.verlet_velocities.input.masses = ip.structure.get_masses
        g.verlet_velocities.input.time_step = ip.time_step
        g.verlet_velocities.input.temperature = ip.temperature
        g.verlet_velocities.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # clock
        g.clock.input.default.max_count = ip.n_steps

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'energy_pot': ~gp.calc_static.output.energy_pot[-1],
            'energy_kin': ~gp.verlet_velocities.output.energy_kin[-1],
            'positions': ~gp.verlet_positions.output.positions[-1],
            'velocities': ~gp.verlet_velocities.output.velocities[-1],
            'forces': ~gp.calc_static.output.forces[-1],
            'pressure': ~gp.barostat.output.pressure[-1],
            'volume': ~gp.calc_static.output.volume[-1]
        }


class ProtoMD(Protocol, MolecularDynamics, ABC):
    pass


class ConfinedMD(MolecularDynamics):
    """
    Similar to MolecularDynamics protocol, ConfinedMD performs MD on a structure. The difference, is that the
    atoms are confined to their lattice sites. This is especially helpful when vacancies are present in the
    structure, and atoms diffuse via the vacancies. This protocol prevents this diffusion from happening.
    """

    DefaultWhitelist = {
    }

    def __init__(self, **kwargs):
        super(ConfinedMD, self).__init__(**kwargs)

        # Protocol defaults
        id_ = self.input.default
        id_.total_steps = 0
        id_.divisor = 1
        id_.thermalized = False
        id_.sampling_period = 1
        id_.thermalization_steps = 0
        id_.crystal_structure = 'fcc'
        id_.lattice_site = [0., 0., 0]
        id_.pressure =None

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.initial_velocities = RandomVelocity()
        g.initial_forces = Zeros()
        g.initial_pressures = Zeros()
        g.check_steps = IsGEq()
        g.clock = Counter()
        g.barostat = BerendsenBarostat()
        g.verlet_positions = VerletPositionUpdate()
        g.reflect_atoms = SphereReflectionPeratom()
        g.calc_static = ExternalHamiltonian()
        g.verlet_velocities = VerletVelocityUpdate()
        g.running_average_positions = PositionsRunningAverage()
        g.check_thermalized = IsGEq()
        g.running_average_forces = WelfordOnline()
        g.nn = NearestNeighbors()
        g.running_average_nn_distance = WelfordOnline()
        g.running_average_nn_forces = WelfordOnline()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.initial_velocities,
            g.initial_forces,
            g.initial_pressures,
            g.check_steps, 'false',
            g.barostat,
            g.verlet_positions,
            g.reflect_atoms,
            g.calc_static,
            g.verlet_velocities,
            g.running_average_positions,
            g.check_thermalized, 'true',
            g.running_average_forces,
            g.nn,
            g.running_average_nn_distance,
            g.running_average_nn_forces,
            g.clock,
            g.check_steps
        )
        g.make_edge(g.check_thermalized, g.clock, 'false')
        g.starting_vertex = g.initial_velocities
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # initial_velocities
        g.initial_velocities.input.temperature = ip.temperature
        g.initial_velocities.input.masses = ip.structure.get_masses
        g.initial_velocities.input.overheat_fraction = ip.overheat_fraction

        # initial_forces
        g.initial_forces.input.shape = ip.structure.positions.shape

        # initial_pressures
        g.initial_pressures.input.shape = ip.structure.cell.shape

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # barostat
        g.barostat.input.default.box_pressure = gp.initial_pressures.output.zeros[-1]
        g.barostat.input.default.structure = ip.structure
        g.barostat.input.default.energy_kin = ip.energy_kin
        g.barostat.input.default.previous_volume = ip.previous_volume
        g.barostat.input.default.positions = ip.structure.positions

        g.barostat.input.box_pressure = gp.calc_static.output.pressures[-1]
        g.barostat.input.structure = gp.barostat.output.structure[-1]
        g.barostat.input.energy_kin = gp.verlet_velocities.output.energy_kin[-1]
        g.barostat.input.previous_volume = gp.calc_static.output.volume[-1]
        g.barostat.input.positions = gp.reflect_atoms.output.positions[-1]

        g.barostat.input.pressure = ip.pressure
        g.barostat.input.temperature = ip.temperature
        g.barostat.input.time_step = ip.time_step
        g.barostat.input.pressure_damping_timescale = ip.pressure_damping_timescale
        g.barostat.input.compressibility = ip.compressibility
        g.barostat.input.style = ip.style

        # verlet_positions
        g.verlet_positions.input.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.verlet_positions.input.default.forces = gp.initial_forces.output.zeros[-1]

        g.verlet_positions.input.positions = gp.barostat.output.positions[-1]
        g.verlet_positions.input.velocities = gp.verlet_velocities.output.velocities[-1]
        g.verlet_positions.input.forces = gp.calc_static.output.forces[-1]

        g.verlet_positions.input.masses = ip.structure.get_masses
        g.verlet_positions.input.time_step = ip.time_step
        g.verlet_positions.input.temperature = ip.temperature
        g.verlet_positions.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # reflect individual atoms which stray too far
        g.reflect_atoms.input.default.previous_positions = ip.structure.positions
        g.reflect_atoms.input.default.previous_velocities = gp.initial_velocities.output.velocities[-1]
        g.reflect_atoms.input.default.cutoff_distance = ip.reflection_cutoff_distance

        g.reflect_atoms.input.reference_positions = ip.structure.positions
        g.reflect_atoms.input.previous_positions = gp.barostat.output.positions[-1]
        g.reflect_atoms.input.previous_velocities = gp.reflect_atoms.output.velocities[-1]
        g.reflect_atoms.input.positions = gp.verlet_positions.output.positions[-1]
        g.reflect_atoms.input.velocities = gp.verlet_positions.output.velocities[-1]

        g.reflect_atoms.input.cell = ip.structure.cell
        g.reflect_atoms.input.pbc = ip.structure.pbc

        # calc_static
        g.calc_static.input.ref_job_full_path = ip.ref_job_full_path
        g.calc_static.input.structure = gp.barostat.output.structure[-1]
        g.calc_static.input.cell = gp.barostat.output.structure[-1].cell
        g.calc_static.input.positions = gp.reflect_atoms.output.positions[-1]

        # verlet_velocities
        g.verlet_velocities.input.velocities = gp.verlet_positions.output.velocities[-1]
        g.verlet_velocities.input.forces = gp.calc_static.output.forces[-1]

        g.verlet_velocities.input.masses = ip.structure.get_masses
        g.verlet_velocities.input.time_step = ip.time_step
        g.verlet_velocities.input.temperature = ip.temperature
        g.verlet_velocities.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # running_average_positions
        g.running_average_positions.input.default.thermalized = ip.thermalized
        g.running_average_positions.input.default.total_steps = ip.total_steps
        g.running_average_positions.input.default.divisor = ip.divisor
        g.running_average_positions.input.default.running_average_positions = gp.reflect_atoms.output.positions[-1]

        g.running_average_positions.input.thermalized = gp.running_average_positions.output.thermalized[-1]
        g.running_average_positions.input.total_steps = gp.running_average_positions.output.total_steps[-1]
        g.running_average_positions.input.divisor = gp.running_average_positions.output.divisor[-1]
        g.running_average_positions.input.running_average_positions = \
            gp.running_average_positions.output.running_average_positions[-1]
        g.running_average_positions.input.positions = gp.reflect_atoms.output.positions[-1]
        g.running_average_positions.input.cell = gp.barostat.output.structure[-1].cell
        g.running_average_positions.input.pbc = ip.structure.pbc
        g.running_average_positions.input.thermalization_steps = ip.thermalization_steps
        g.running_average_positions.input.initial_positions = ip.structure.positions

        # check_thermalized
        g.check_thermalized.input.target = gp.clock.output.n_counts[-1]
        g.check_thermalized.input.threshold = ip.thermalization_steps

        # running_average_forces
        g.running_average_forces.input.sample = gp.calc_static.output.forces[-1]

        # nearest_neighbor_distances
        g.nn.input.lattice_site = ip.lattice_site
        g.nn.input.nn_indices = ip.nn_indices
        g.nn.input.positions = gp.reflect_atoms.output.positions[-1]
        g.nn.input.forces = gp.calc_static.output.forces[-1]
        g.nn.input.cell = gp.barostat.output.structure[-1].cell
        g.nn.input.pbc = ip.structure.pbc

        # running_average_nn_distance
        g.running_average_nn_distance.input.sample = gp.nn.output.nn_distances[-1]

        # running_average_nn_forces
        g.running_average_nn_forces.input.sample = gp.nn.output.nn_forces[-1]

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'energy_pot': ~gp.calc_static.output.energy_pot[-1],
            'energy_kin': ~gp.verlet_velocities.output.energy_kin[-1],
            'positions': ~gp.reflect_atoms.output.positions[-1],
            'velocities': ~gp.verlet_velocities.output.velocities[-1],
            'forces': ~gp.calc_static.output.forces[-1],
            'pressure': ~gp.barostat.output.pressure[-1],
            'volume': ~gp.calc_static.output.volume[-1],
            'running_average_positions': ~gp.running_average_positions.output.running_average_positions[-1],
            'running_average_forces': ~gp.running_average_forces.output.mean[-1],
            'nn_distances': ~gp.running_average_nn_distance.output.mean[-1],
            'nn_forces': ~gp.running_average_nn_forces.output.mean[-1]
        }


class ProtoConfinedMD(Protocol, ConfinedMD, ABC):
    pass


class HarmonicMD(CompoundVertex):
    """

    """

    DefaultWhitelist = {
    }

    def __init__(self, **kwargs):
        super(HarmonicMD, self).__init__(**kwargs)

        # Protocol defaults
        id_ = self.input.default
        id_.temperature = None
        id_.energy_kin = None
        id_.n_steps = 100
        id_.time_step = 1.
        id_.temperature_damping_timescale = 100.
        id_.overheat_fraction = 2
        id_.spring_constant = None
        id_.force_constants = None

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.initial_velocities = RandomVelocity()
        g.initial_forces = Zeros()
        g.initial_pressures = Zeros()
        g.check_steps = IsGEq()
        g.clock = Counter()
        g.verlet_positions = VerletPositionUpdate()
        g.calc_harmonic = HarmonicHamiltonian()
        g.verlet_velocities = VerletVelocityUpdate()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.initial_velocities,
            g.initial_forces,
            g.initial_pressures,
            g.check_steps, 'false',
            g.verlet_positions,
            g.calc_harmonic,
            g.verlet_velocities,
            g.clock,
            g.check_steps
        )
        g.starting_vertex = g.initial_velocities
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # initial_velocity
        g.initial_velocities.input.temperature = ip.temperature
        g.initial_velocities.input.masses = ip.structure.get_masses
        g.initial_velocities.input.overheat_fraction = ip.overheat_fraction

        # initial_forces
        g.initial_forces.input.shape = ip.structure.positions.shape

        # initial_pressures
        g.initial_pressures.input.shape = ip.structure.cell.array.shape

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        # verelt_positions
        g.verlet_positions.input.default.positions = ip.structure.positions
        g.verlet_positions.input.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.verlet_positions.input.default.forces = gp.initial_forces.output.zeros[-1]

        g.verlet_positions.input.positions = gp.verlet_positions.output.positions[-1]
        g.verlet_positions.input.velocities = gp.verlet_velocities.output.velocities[-1]
        g.verlet_positions.input.forces = gp.calc_harmonic.output.forces[-1]

        g.verlet_positions.input.masses = ip.structure.get_masses
        g.verlet_positions.input.time_step = ip.time_step
        g.verlet_positions.input.temperature = ip.temperature
        g.verlet_positions.input.temperature_damping_timescale = ip.temperature_damping_timescale

        # calc_harmonic
        g.calc_harmonic.input.positions = gp.verlet_positions.output.positions[-1]
        g.calc_harmonic.input.home_positions = ip.structure.positions
        g.calc_harmonic.input.cell = ip.structure.cell.array
        g.calc_harmonic.input.pbc = ip.structure.pbc
        g.calc_harmonic.input.spring_constant = ip.spring_constant
        g.calc_harmonic.input.force_constants = ip.force_constants

        # verlet_velocities
        g.verlet_velocities.input.velocities = gp.verlet_positions.output.velocities[-1]
        g.verlet_velocities.input.forces = gp.calc_harmonic.output.forces[-1]

        g.verlet_velocities.input.masses = ip.structure.get_masses
        g.verlet_velocities.input.time_step = ip.time_step
        g.verlet_velocities.input.temperature = ip.temperature
        g.verlet_velocities.input.temperature_damping_timescale = ip.temperature_damping_timescale

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'energy_pot': ~gp.calc_harmonic.output.energy_pot[-1],
            'energy_kin': ~gp.verlet_velocities.output.energy_kin[-1],
            'positions': ~gp.verlet_positions.output.positions[-1],
            'velocities': ~gp.verlet_velocities.output.velocities[-1],
            'forces': ~gp.calc_harmonic.output.forces[-1],
        }


class ProtoHarmonicMD(Protocol, HarmonicMD, ABC):
    pass


class ConfinedHarmonicMD(CompoundVertex):
    """
    Similar to MolecularDynamics protocol, ConfinedHarmonicMD performs harmonic MD on a structure. The difference,
    is that the atoms are confined to their lattice sites. This is especially helpful when vacancies are present in the
    structure, and atoms diffuse via the vacancies. This protocol prevents this diffusion from happening.
    """

    DefaultWhitelist = {
    }

    def __init__(self, **kwargs):
        super(ConfinedHarmonicMD, self).__init__(**kwargs)

        # Protocol defaults
        id_ = self.input.default
        id_.time_step = 1.
        id_.overheat_fraction = 2.
        id_.damping_timescale = 100.
        id_.sampling_period = 1
        id_.thermalization_steps = 10
        id_.relax_endpoints = True
        id_.reset = False
        id_.crystal_structure = 'fcc'
        id_.lattice_site = [0., 0., 0]
        id_.spring_constant = 1.

    def define_vertices(self):
        # Graph components
        g = self.graph
        g.initial_velocities = RandomVelocity()
        g.initial_forces = Zeros()
        g.check_steps = IsGEq()
        g.verlet_positions = VerletPositionUpdate()
        g.reflect_atoms = SphereReflectionPeratom()
        g.harmonic = HarmonicHamiltonian()
        g.verlet_velocities = VerletVelocityUpdate()
        g.check_thermalized = IsGEq()
        g.check_sampling_period = ModIsZero()
        g.running_average = PositionsRunningAverage()
        g.nn = NearestNeighbors()
        g.average_distance = WelfordOnline()
        g.clock = Counter()

    def define_execution_flow(self):
        # Execution flow
        g = self.graph
        g.make_pipeline(
            g.initial_velocities,
            g.initial_forces,
            g.check_steps, 'false',
            g.clock,
            g.verlet_positions,
            g.reflect_atoms,
            g.harmonic,
            g.verlet_velocities,
            g.check_thermalized, 'true',
            g.check_sampling_period, 'true',
            g.running_average,
            g.nn,
            g.average_distance,
            g.check_steps
        )
        g.make_edge(g.check_thermalized, g.check_steps, 'false')
        g.make_edge(g.check_sampling_period, g.check_steps, 'false')
        g.starting_vertex = g.initial_velocities
        g.restarting_vertex = g.check_steps

    def define_information_flow(self):
        # Data flow
        g = self.graph
        gp = Pointer(self.graph)
        ip = Pointer(self.input)

        # initial_velocities
        g.initial_velocities.input.temperature = ip.temperature
        g.initial_velocities.input.masses = ip.structure.get_masses
        g.initial_velocities.input.overheat_fraction = ip.overheat_fraction

        # initial_forces
        g.initial_forces.input.shape = ip.structure.positions.shape

        # check_steps
        g.check_steps.input.target = gp.clock.output.n_counts[-1]
        g.check_steps.input.threshold = ip.n_steps

        self.set_graph_archive_clock(gp.clock.output.n_counts[-1])

        # verlet_positions
        g.verlet_positions.input.time_step = ip.time_step
        g.verlet_positions.input.masses = ip.structure.get_masses
        g.verlet_positions.input.temperature = ip.temperature
        g.verlet_positions.input.temperature_damping_timescale = ip.temperature_damping_timescale

        g.verlet_positions.input.default.positions = ip.structure.positions
        g.verlet_positions.input.default.velocities = gp.initial_velocities.output.velocities[-1]
        g.verlet_positions.input.default.forces = gp.initial_forces.output.zeros[-1]

        g.verlet_positions.input.positions = gp.reflect_atoms.output.positions[-1]
        g.verlet_positions.input.velocities = gp.verlet_velocities.output.velocities[-1]
        g.verlet_positions.input.forces = gp.harmonic.output.forces[-1]

        # reflect individual atoms which stray too far
        g.reflect_atoms.input.cutoff_distance = ip.reflection_cutoff_distance
        g.reflect_atoms.input.cell = ip.structure.cell
        g.reflect_atoms.input.pbc = ip.structure.pbc

        g.reflect_atoms.input.reference_positions = ip.structure.positions

        g.reflect_atoms.input.default.previous_positions = ip.structure.positions
        g.reflect_atoms.input.default.previous_velocities = gp.initial_velocities.output.velocities[-1]

        g.reflect_atoms.input.previous_positions = gp.reflect_atoms.output.positions[-1]
        g.reflect_atoms.input.previous_velocities = gp.reflect_atoms.output.velocities[-1]

        g.reflect_atoms.input.positions = gp.verlet_positions.output.positions[-1]
        g.reflect_atoms.input.velocities = gp.verlet_positions.output.velocities[-1]

        # calc_harmonic
        g.harmonic.input.spring_constant = ip.spring_constant
        g.harmonic.input.home_positions = ip.structure.positions
        g.harmonic.input.positions = gp.reflect_atoms.output.positions[-1]
        g.harmonic.input.cell = ip.structure.cell
        g.harmonic.input.pbc = ip.structure.pbc

        # verlet_velocities
        g.verlet_velocities.input.time_step = ip.time_step
        g.verlet_velocities.input.masses = ip.structure.get_masses
        g.verlet_velocities.input.temperature = ip.temperature
        g.verlet_velocities.input.temperature_damping_timescale = ip.temperature_damping_timescale

        g.verlet_velocities.input.velocities = gp.reflect_atoms.output.velocities[-1]
        g.verlet_velocities.input.forces = gp.harmonic.output.forces[-1]

        # check_thermalized
        g.check_thermalized.input.target = gp.clock.output.n_counts[-1]
        g.check_thermalized.input.threshold = ip.thermalization_steps

        # check_sampling_period
        g.check_sampling_period.input.target = gp.clock.output.n_counts[-1]
        g.check_sampling_period.input.default.mod = ip.sampling_period

        # running_average_positions
        g.running_average.input.default.running_average_list = gp.reflect_atoms.output.positions[-1]
        g.running_average.input.running_average_list = gp.running_average.output.running_average_list[-1]
        g.running_average.input.positions_list = gp.reflect_atoms.output.positions[-1]
        g.running_average.input.sampling_period = ip.sampling_period
        g.running_average.input.reset = ip.reset
        g.running_average.input.relax_endpoints = ip.relax_endpoints
        g.running_average.input.cell = ip.structure.cell
        g.running_average.input.pbc = ip.structure.pbc

        # nearest_neighbor_distances
        g.nn.input.structure = ip.structure
        g.nn.input.crystal_structure = ip.crystal_structure
        g.nn.input.lattice_site = ip.lattice_site
        g.nn.input.atoms_positions = gp.running_average.output.running_average_list[-1]

        # average_nearest_neighbor_distances
        g.average_distance.input.sample = gp.nn.output.NN_distance[-1]

    def get_output(self):
        gp = Pointer(self.graph)
        return {
            'positions': ~gp.reflect_atoms.output.positions[-1],
            'velocities': ~gp.verlet_velocities.output.velocities[-1],
            'forces': ~gp.harmonic.output.forces[-1],
            'running_average_positions': ~gp.running_average.output.running_average_list[-1],
            'nn_distance_mean': ~gp.average_distance.output.mean[-1],
            'nn_distance_std': ~gp.average_distance.output.std[-1]
        }


class ProtoConfinedHarmonicMD(Protocol, ConfinedHarmonicMD):
    pass