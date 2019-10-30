from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator
from typing import List

class DtnMBLTPDuctParser(DtnAbstractParser):
    """ Parser for Multiband LTP duct YAML configuration parameters """
    # Frequency bands of this multiband duct
    bands: List[str]

    # LTP block aggregation size limit
    agg_size_limit: float

    # LTP data segment size
    segment_size: float

    # LTP report timer
    report_timer: float

    # LTP checkpoint timer
    checkpoint_timer: float

    @validator('bands')
    def validate_bands(cls, band, *, values, **kwargs):
        # Check that a radio is specified for this band
        if band not in values['params'][values['tag']]:
            raise TypeError(f'Sub-tag "{band}" is not defined in duct "{values["tag"]}".')

        # Check that the radios exist
        radio_type = values['params'][values['tag']][band]
        if radio_type not in values['params']:
            raise TypeError(f'Radio "{radio_type}" is not defined but needed for duct "{values["tag"]}".')

        return band

