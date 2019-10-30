from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat, PositiveFloat, PositiveInt

class DtnCodedRadioParser(DtnAbstractParser):
    """ Parser for YAML configuration parameters of DtnBasicRadio """
    # Data rate in [bps]
    rate : PositiveFloat

    # Frame error rate
    FER : confloat(gt=-0.000000001, lt=1) = 0.0

    # Frame size in [bits]
    frame_size: PositiveInt

    # Coding rate
    code_rate: confloat(gt=0, lt=1.0000001)

    # Joules/bit in the link
    J_bit : confloat(gt=-0.0000001) = 0.0
