from .DtnAbstractParser import DtnAbstractParser
from pydantic import confloat, PositiveFloat

class DtnBasicRadioParser(DtnAbstractParser):
    """ Validator for YAML configuration parameters of DtnBasicRadio """
    # Data rate in [bps]
    rate : PositiveFloat

    # Bit error rate
    BER : confloat(gt=-0.000000001, lt=1) = 0.0

    # Joules/bit in the link
    J_bit : confloat(gt=-0.0000001) = 0.0
