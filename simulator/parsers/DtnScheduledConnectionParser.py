from .DtnAbstractParser import DtnAbstractParser
from typing import Dict
from pydantic import validator

class DtnScheduledConnectionParser(DtnAbstractParser):
    """ Parser for YAML configuration parameters of DtnStaticConnection """
    # Dictionary of ducts in this connection
    ducts : Dict[str, str]

    # Name of mobility model
    mobility_model : str

    @validator('ducts', whole=True)
    def validate_ducts(cls, ducts, *, values, **kwargs):
        # When validating a dictionary, Pydantic first gives you the keys and
        # values to validate individually. This is currently a known Pydantic
        # bug (see Pydantic github, issue #254)# simple workaround.
        if not isinstance(ducts, dict):
            return ducts

        # Check that the ducts are defined
        for duct in ducts.values():
            if duct not in values['params']:
                raise TypeError(f'Tag "{duct}" is not defined in YAML file.')

        return ducts

    @validator('mobility_model')
    def validate_mobility_model(cls, mobility_model, *, values, **kwargs):
        return DtnScheduledConnectionParser._validate_tag_exitance(cls, mobility_model, values)