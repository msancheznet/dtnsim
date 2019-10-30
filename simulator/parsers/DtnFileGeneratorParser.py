from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat, PositiveFloat
from typing import Optional

class DtnFileGeneratorParser(DtnAbstractParser):
    """ Validator for a file generator """
    # File size in [bits]
    size: PositiveFloat

    # Data Tyoe
    data_type: Optional[str] = 'file'

    # Start time of the file transmission (in simulation time)
    tstart: confloat(gt=-1) = 0

    # Bundle size in bits
    bundle_size: PositiveFloat

    # Bundle Time-to-live (TTL) in [sec]
    bundle_TTL: PositiveFloat = float('inf')

    # Data criticality. If True, then network will be flooded
    # with this data
    critical: bool = False

    # Destination node. If none, then the destination of the bundle
    # will be chosen at random from all other nodes in the network
    destination: Optional[str] = None

    # How many times to send the file
    repeat: int = 1

    # How long in [sec] to wait between sending the files again
    wait: float = 0.0