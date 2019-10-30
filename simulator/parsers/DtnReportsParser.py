from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator
from typing import List, Optional
import simulator.reports as rp

class DtnReportsParser(DtnAbstractParser):
    reports: Optional[List[str]] = None

    @validator('reports', whole=True)
    def validate_report_defined(cls, reports):
        if not reports:
            raise ValueError('At least one report must be provided')

        for report in reports:
            if report not in dir(rp):
                raise TypeError(f'Report "{report}" not defined in folder /reports')

        return set() if not reports else set(reports)