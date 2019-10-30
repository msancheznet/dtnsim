from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator

class DtnLTPDuctParser(DtnAbstractParser):
    """ Parser for LTP duct YAML configuration parameters """
    # Name of radio
    radio: str

    # LTP block aggregation size limit
    agg_size_limit: float

    # LTP data segment size
    segment_size: float

    # LTP report timer
    report_timer: float

    # LTP checkpoint timer
    checkpoint_timer: float

    @validator('radio')
    def radio_validator(cls, radio, *, values, **kwargs):
        return DtnLTPDuctParser._validate_tag_exitance(cls, radio, values)