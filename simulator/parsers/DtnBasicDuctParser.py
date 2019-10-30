from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator

class DtnBasicDuctParser(DtnAbstractParser):
    """ Parser for DtnBasicDuct's YAML configuration parameters """
    # Radio type
    radio : str

    @validator('radio')
    def validate_radios(cls, radio, *, values, **kwargs):
        return DtnBasicDuctParser._validate_tag_exitance(cls, radio, values)