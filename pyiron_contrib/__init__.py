# from pyiron_contrib.protocol.generic import Protocol
from pyiron_contrib.protocol.compound.minimize import ProtocolMinimize
from pyiron_contrib.protocol.compound.molecular_dynamics import ProtocolMD
from pyiron_contrib.protocol.compound.nudged_elastic_band import ProtocolNEB
# from pyiron_contrib.protocol.compound.tild import HarmonicTILD, VacancyTILD
# from pyiron_contrib.protocol.compound.finite_temperature_string import StringRelaxation, VirtualWork, \
#     Milestoning, VirtualWorkParallel, VirtualWorkSerial, VirtualWorkFullStep
from pyiron_contrib.protocol.compound.qmmm import ProtocolQMMM
from pyiron_contrib.protocol.compound.tild import ProtocolHarmonicTILD, ProtocolHarmonicTILDParallel
from pyiron_contrib.protocol.compound.minimize_bfgs import ProtocolMinimizeBFGS

# protocol is a magic class after this one we have to Register
# from pyiron_contrib.protocol.utils.types import PyironJobTypeRegistryMetaType
# PyironJobTypeRegistryMetaType.inject_dynamic_types()
__all__ = [
    'ProtocolMinimize',
    'ProtocolMD',
    'ProtocolNEB',
    'ProtocolQMMM',
    'ProtocolHarmonicTILD',
    'ProtocolHarmonicTILDParallel',
    'ProtocolMinimizeBFGS'
]
