import abc
from collections import defaultdict
import numpy as np
from .DtnCore import Message

class LtpSegment(Message, metaclass=abc.ABCMeta):
    """ Abstract LTP segments that is then specialized into a Data Segment (DS),
        Report Segment (RS) or Report Acknowledgement Segment (RA). Other segments
        such as session cancellation or cancellation ack are not defined here.
    """
    _segment_types = ['DS', 'RS', 'RA', 'CS']

    def __init__(self, type, session_id):
        # Call parent constructor
        super(LtpSegment, self).__init__()

        # Check the provided type
        if type not in LtpSegment._segment_types:
            raise ValueError('LTP segment type can only be {}'.format(LtpSegment._segment_types))

        # Set the LTP session that this segment belongs to
        self.session_id = session_id

        # Set this segment type
        self.type = type

        # Set the size to None. Its subclasses must override this value
        self.size = None

    @property
    def mid(self):
        return (hex(id(self)), 0)

    @property
    def num_bits(self):
        return self.size

    def __str__(self):
        return '<LtpSegment>'

class LtpDataSegment(LtpSegment):
    """ An LTP Data Segment (see page 16, rfc 5326) """

    def __init__(self, session_id, offset, length, checkpoint=None, report=None):
        """ Class constructor

            :param bid: Block id = block hash
            :param offset: Offset from start of block in Bytes
            :param length: Length of data in this segment in Bytes
            :param checkpoint: Checkpoint id if this segment is checkpoint. Otherwise None
            :param report: Report serial number if this segment is issued in response to a
                           report segment
        """
        # Call parent constructor
        super(LtpDataSegment, self).__init__("DS", session_id)

        # Store variables
        self.offset     = offset
        self.length     = length
        self.checkpoint = checkpoint
        self.report     = report

        # Size in bytes of this segment. Assume 10 bytes of overhead
        self.size = np.ceil(self.length + 10)

    @property
    def is_checkpoint(self):
        return self.checkpoint is not None

    def __str__(self):
        return '<LtpDataSegment ({}, {}, {})>'.format(self.offset, self.length, self.checkpoint)

class LtpReportSegment(LtpSegment):
    """ An LTP Report Segment (see page 17, rfc 5326) """

    # Static variable to keep track of report serial numbers
    # It is a dictionary indexed by checkpoint serial number
    report_counter = defaultdict(int)

    def __init__(self, session_id):
        # Call parent constructor
        super(LtpReportSegment, self).__init__("RS", session_id)

        # Store variables
        self.id         = None
        self.checkpoint = None
        self.lower_bnd  = float('inf')  # Initial value
        self.upper_bnd  = -float('inf') # Initial value
        self.claims     = set()         # A claim is a tuple of format (offset, length)

        # Size in bytes of this segment. Assume 25 bytes constant
        self.size = 25.0

    @property
    def num_claims(self):
        return len(self.claims)

    def __str__(self):
        s  = '<LtpReportSegment {} (lb={}, ub={})\n'.format(self.id, self.lower_bnd,self.upper_bnd)
        for i, claim in enumerate(self.claims):
            s += ' Claim {}: offset={}, length={}\n'.format(i+1, claim[0], claim[1])
        return s[0:-1] + '>'

    def __repr__(self):
        return '<LtpReportSegment {} (lb={}, ub={})>'.format(self.id, self.lower_bnd, self.upper_bnd)

class LtpReportAcknowledgementSegment(LtpSegment):
    def __init__(self, session_id, report_id):
        # Call parent constructor
        super(LtpReportAcknowledgementSegment, self).__init__("RA", session_id)

        # Store variables
        self.report_id = report_id

        # Size of this report. Assume 10 bytes
        self.size = 10.0

    def __str__(self):
        return '<LtpReportAck {}>'.format(self.report_id)

class LtpCancelSessionSegment(LtpSegment):
    """ This is not equivalent to the cancel sessions in the LTP specification.
        It is a convenient way to signal the ``run_ltp_session`` of either a
        DtnOutductLTP or DtnInductLTP that there has been an error during transmission
        of this block and this session should be cancelled and the bundles in the block
        sent to re-routers.
    """
    def __init__(self, session_id):
        super(LtpCancelSessionSegment, self).__init__("CS", session_id)