
from collections import defaultdict
from simulator.ducts.DtnAbstractDuctLTP import DtnAbstractDuctLTP
from simulator.core.DtnSegments import LtpReportSegment
from simulator.core.DtnPriorityQueue import DtnPriorityQueue
import pandas as pd

class DtnInductLTP(DtnAbstractDuctLTP):
    """ An LTP induct """
    duct_type = 'induct'

    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnInductLTP, self).__init__(env, name, parent, neighbor)

        # Counter for the report segment ids, one per LTP session
        self.report_counter = {}

        # Dictionary with report segments pending acknowledgement, one per LTP session
        # {session_id: rs.id: rs}
        self.pending_ack = defaultdict(dict)

        # UNCOMMENT FOR TESTING
        # self.counter = 0      # Counts num of bundles delivered

    @property
    def stored(self):
        df = self.radio.stored
        d  = {}
        for sid, q in self.ltp_queues.items():
            dff = q.stored
            if dff.empty: continue
            dff['where'] = 'LTP session {}'.format(sid)
            d[sid] = dff
        return pd.concat(pd.concat(d), df) if d else df

    def initialize(self, peer, report_timer=1e10, **kwargs):
        # The timer that triggers re-tx of a report segment if you do not hear from peer
        self.report_timer = float(report_timer)

        # Call parent initialization
        super(DtnInductLTP, self).initialize(peer, **kwargs)

    def run(self):
        while self.is_alive:
            # Wait until you have received a segment
            segment = yield from self.in_queue.get()

            # Get the session id for this segment
            sid = segment.session_id

            # If a session is not already running, create it
            if not self.is_session(sid): self.initialize_ltp_session(sid)

            # Direct the segment to the appropriate ltp_receive process
            # This is either a DS or RA, so no need to put it expedited
            yield from self.ltp_queues[sid].put(segment, 1)

    def initialize_ltp_session(self, session_id):
        # Create a new queue
        self.ltp_queues[session_id] = DtnPriorityQueue(self.env)

        # Initialize the report counter
        self.report_counter[session_id] = 0

        # Start the process for managing this LTP session
        # Note: This is a non-blocking call since you can have multiple LTP sessions
        #       running at the same time
        self.env.process(self.run_ltp_session(session_id))

    def finalize_ltp_session(self, session_id):
        # Delete global variables for this session
        self.report_counter.pop(session_id)
        self.pending_ack.pop(session_id)
        self.ltp_queues.pop(session_id)

    def run_ltp_session(self, session_id):
        """ Wait for segments to reconstruct a block. If a checkpoint is created,
            respond with a Report Segment
        """
        # Initialize variables
        first_checkpt  = True
        to_receive     = 0.0
        received       = 0.0
        rx_checkpoints = set()
        success        = False                          # If True, you have received all segments for this block
        rs             = LtpReportSegment(session_id)

        # Run until all bits in this block have been acknowledged
        while self.is_alive:
            # Wait until you have received a segment
            segment = yield from self.ltp_queues[session_id].get()

            # If this segment has errors, discard it, you cannot understand its contents
            if segment.has_errors: continue

            # If this is a Cancel Segment report, then exit
            if segment.type == 'CS': break

            # If this is a report acknowledgement segment, process it separately
            if segment.type == 'RA':
                self.process_report_acknowledgement(session_id, segment)

                # If you have not received acknowledgement from all report segments, wait
                if self.pending_ack[session_id]: continue

                # If you are not ready to exit because you are missing data, wait
                if not success: continue

                # At this point you are ready to exit this LTP session
                break

            # If you have succeed already, just keep waiting for a RA. That is all left
            # in this session.
            if success: continue

            # If you have already seen this checkpoint, continue. You need to check
            # this here because this segment could be a duplicate checkpoint sent
            # by a timer.
            if segment in rx_checkpoints: continue

            # If this segment has an offset that is lower than the current report's lower
            # bound, use that one. It means that data segments for a given checkpoint have
            # been received out of order
            if segment.offset < rs.lower_bnd: rs.lower_bnd = segment.offset

            # Add a reception claim. NOTE: This is different from rfc 5350!!! The offset of
            # the claim is relative to the start of the block, whereas in the spec it is
            # relative to RS' lower bound
            rs.claims.add((segment.offset, segment.length))

            # Add data volume received
            received += segment.length

            # If this segment is not a checkpoint, you are done
            if not segment.is_checkpoint: continue

            # At this point you know that this is a checkpoint and it is not a duplicate.
            # Therefore, add it to set of seen checkpoints
            rx_checkpoints.add(segment)

            # If this is the first time you see a checkpoint, it will tell you the block
            # size. This is only true because of the deferred-ack mode
            if first_checkpt:
                to_receive    = segment.offset + segment.length
                first_checkpt = False

            # This segment is a checkpoint, you must issue a Report Segment in response
            rs.checkpoint = segment.checkpoint
            rs.upper_bnd  = segment.offset + segment.length
            rs.id         = self.new_report_id(session_id)

            # Enqueue the report to be sent
            self.radio.put(self.neighbor, rs, self.peer, self.transmit_mode)

            # Mark this report segment as pending acknowledgement
            self.pending_ack[session_id][rs.id] = rs

            # Start the timer for the report segment
            self.env.process(self.start_report_timer(session_id, rs.id))

            # If you have received all data in the block, you are ready to exit
            success = received >= to_receive

            # If you are ready to exit, deliver the block to the DTN node. Do not wait
            # for the last report acknowledgement since that would be a waste of time
            # in the presence of long RTTs
            if success: self.deliver_block(session_id)

            # Reset the Report Segment
            rs = LtpReportSegment(session_id)

        # Tear down this LTP session
        self.finalize_ltp_session(session_id)

    def new_report_id(self, session_id):
        # Update the report counter
        self.report_counter[session_id] += 1

        # Return the current value
        return self.report_counter[session_id]

    def deliver_block(self, session_id):
        # Get actual block from peer outduct. This does not actually happen,
        # it is just a shortcut for the simulation. Also, you can do this
        # because all connections have propagation delays > 1 second and therefore
        # it is impossible that you have already received the corresponding report
        # acknowledgment
        block = self.peer.block[session_id]

        # UNCOMMENT FOR TESTING
        #self.counter += 1
        #print(self.t, self.counter, 'block delivered')

        # Deliver bundles to the DTN node
        for bundle in block: self.parent.forward(bundle)

    def process_report_acknowledgement(self, session_id, segment):
        # If this report ack does not point to a report in pending, it was
        # previously eliminated by another report ack. Skip
        if segment.report_id not in self.pending_ack[session_id]: return

        # Mark this report segment as no longer pending acknowledgment
        del self.pending_ack[session_id][segment.report_id]

    def start_report_timer(self, session_id, rid):
        # Wait until timer expires
        yield self.env.timeout(self.report_timer)

        # If this session no longer exists, return
        if not self.is_session(session_id): return

        # If this report segment has already been acknowledged, return
        if rid not in self.pending_ack[session_id]: return

        # Get the missing report
        rs = self.pending_ack[session_id][rid]

        # Reset the ``has_errors`` flag
        rs.has_errors = False

        # Re-send report segment
        self.radio.put(self.neighbor, rs, self.peer, self.transmit_mode)

        # Start the timer for the report segment
        self.env.process(self.start_report_timer(session_id, rs.id))

    def __str__(self):
        return "<LtpInduct {}-{}>".format(self.neighbor, self.parent.nid)