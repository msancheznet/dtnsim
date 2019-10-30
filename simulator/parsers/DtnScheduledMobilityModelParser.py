from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat

class DtnScheduledMobilityModelParser(DtnAbstractParser):
    """ Parser for YAML configuration parameters of DtnScheduledMobilityModel """
    # Excel listing all contacts
    contacts : str

    # Excel listing all ranges
    ranges : str

