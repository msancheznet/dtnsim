from .DtnAbstractParser import DtnAbstractParser
from typing import Dict, Optional
from pydantic import validator

class DtnStaticConnectionParser(DtnAbstractParser):
    """ Parser for YAML configuration parameters of DtnStaticConnection """
    # Dictionary of ducts in this connection
    ducts : Dict[str, str]

    # Mobility model
    mobility_model : str

    # Propagation delay in [sec]. If not provided, then the simulator
    # will attempt to get it from the mobility model
    prop_delay: Optional[float]

    @validator('ducts', whole=True)
    def validate_ducts(cls, ducts, *, values, **kwargs):
        # When validating a dictionary, Pydantic first gives you the keys and
        # values to validate individually. This is currently a known Pydantic
        # bug (see Pydantic github, issue #254)
        if not isinstance(ducts, dict):
            return ducts

        for duct in ducts.values():
            if duct not in values['params']:
                raise TypeError(f'Tag "{duct}" is not defined in YAML file.')

        return ducts

    @validator('mobility_model')
    def validate_mobility_model(cls, mobility_model, *, values, **kwargs):
        return DtnStaticConnectionParser._validate_tag_exitance(cls, mobility_model, values)