from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat

class DtnStaticMobilityModelParser(DtnAbstractParser):
    """ Parser for YAML configuration parameters of DtnStaticMobilityModel """
    # Propagation delay in [sec]
    prop_delay : confloat(gt=-1e-20) = 0.0
