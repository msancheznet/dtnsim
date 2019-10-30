from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator
from typing import Dict

class DtnDistanceConnectionParser(DtnAbstractParser):
    """ YAML validator for DtnDistanceConnection """
    # Dictionary of ducts in this connection
    ducts: Dict[str, str]

    # Name of mobility model
    mobility_model: str

    # Maximum distance at which the connection is active
    # Units must be consistent with distance units of mobility model
    max_distance: float

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
        return DtnDistanceConnectionParser._validate_tag_exitance(cls, mobility_model, values)