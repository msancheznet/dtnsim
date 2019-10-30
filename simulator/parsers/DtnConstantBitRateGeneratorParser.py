from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat, PositiveFloat
from typing import Optional

class DtnConstantBitRateGeneratorParser(DtnAbstractParser):
    """ Validator for a constant bit rate generator """
    # Generation data rate in [bps]
    rate: PositiveFloat

    # Data Tyoe
    data_type: str = 'file'

    # Duration of this flow in [sec]
    until: PositiveFloat

    # Start time of the flow in simulation time
    tstart: confloat(gt=-1) = 0

    # Bundle size in bits
    bundle_size: PositiveFloat

    # Bundle Time-to-live (TTL)
    bundle_TTL: PositiveFloat = float('inf')

    # Data criticality. If True, then network will be flooded
    # with this data
    critical: bool = False

    # Destination node. If none, then the destination of the bundle
    # will be chosen at random from all other nodes in the network
    destination: Optional[str] = None