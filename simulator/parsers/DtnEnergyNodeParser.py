from .DtnNodeParser import DtnNodeParser
from typing import Optional
from pydantic import PositiveFloat

class DtnEnergyNodeParser(DtnNodeParser):
    """ Parser for DtnEnergyNode's YAML configuration parameters """
    # Battery level at the start of the simulation in [J]
    battery: Optional[PositiveFloat] = float('inf')

    # Rate at which battery level will be updated in [sec]
    battery_rate: Optional[int] = 1