from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat, PositiveFloat
from typing import Optional

class DtnFileBroadcasterParser(DtnAbstractParser):
    """ Validator for a file generator """
    # Data Tyoe
    data_type: str

    # Start time of the file transmission (in simulation time)
    tstart: confloat(gt=-1) = 0

    # Bundle size in bits
    bundle_size: PositiveFloat

    # File size in [bits]
    size: PositiveFloat

    # Bundle Time-to-live (TTL) in [sec]
    bundle_TTL: PositiveFloat

    # Data criticality. If True, then network will be flooded
    # with this data
    critical: bool = False

    # How many times to send the file
    repeat: int = 1

    # How long in [sec] to wait between sending the files again
    wait: float = 0.0