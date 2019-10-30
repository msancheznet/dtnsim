import abc
from pydantic import BaseModel
from typing import Optional

class DtnAbstractParser(BaseModel, metaclass=abc.ABCMeta):
    """ Abstract validator with the default configuration parameters for all
        other parsers.
    """
    # Tag of the YAML file being validated
    tag : Optional[str]

    # Dictionary will all configuration parameters. It will be accessible
    # to any validator using ``values['params']
    params : dict

    class Config:
        # Strip leading/trailing white spaces
        anystr_strip_whitespace = True

        # Force validation of all fields
        validate_all = True

        # Allow any extra values to be parsed. This is done so that DtnNullValidator
        # can parse any parameters and make them available through the . operator to
        # any downstream classes
        allow_extra  = True

        # Validation models should ideally not be mutable (i.e. do not allow __setattr__)
        # However, it is needed in DtnNetworkValidator
        allow_mutation = True

    def _validate_tag_exitance(cls, tag, values):
        """ Check the a given tag is defined in the YAML file """
        if tag not in values['params']:
            raise TypeError(f'Tag "{tag}" is not defined in YAML file.')

        return tag