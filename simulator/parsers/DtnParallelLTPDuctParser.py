from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator
from typing import Dict

class DtnParallelLTPDuctParser(DtnAbstractParser):
    """ Parser for Parallel LTP duct YAML configuration parameters """
    # LTP engines to use in parallel
    engines: Dict[str, str]

    @validator('engines', whole=True)
    def validate_engines(cls, engines, *, values, **kwargs):
        # When validating a dictionary, Pydantic first gives you the keys and
        # values to validate individually. This is currently a known Pydantic
        # bug (see Pydantic github, issue #254)
        if not isinstance(engines, dict):
            return engines

        for engine in engines.values():
            if engine not in values['params']:
                raise TypeError(f'Duct "{engine}" is not defined but needed for duct "{values["tag"]}".')

        return engines