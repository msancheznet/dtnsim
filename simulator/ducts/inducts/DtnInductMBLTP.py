from collections import defaultdict
from copy import deepcopy
import numpy as np
import pandas as pd
from simulator.core.DtnPriorityQueue import DtnPriorityQueue
from simulator.core.DtnSegments import LtpDataSegment, LtpReportSegment
from simulator.ducts.DtnAbstractDuctMBLTP import DtnAbstractDuctMBLTP
from simulator.utils.math_utils import union_intervals

class DtnInductMBLTP(DtnAbstractDuctMBLTP):
    duct_type = 'induct'

    def __init__(self, env, name, parent, neighbor):
        super(DtnInductMBLTP, self).__init__(env, name, parent, neighbor)

        # Counter for the report segment ids, one per LTP session
        self.report_counter = {}

        # Dictionary with report segments pending acknowledgement, one per LTP session
        # {session_id: rs.id: rs}
        self.pending_ack = defaultdict(dict)

        # Indicates the maximum session_id for which a session has been opened. It is
        # updated every time an LTP session is initialized
        self.last_sid = -1

        # UNCOMMENT FOR TESTING
        #self.counter = 0        # Counts the num. of blocks delivered
        #self.delivered = {}     # Records bundles delivered

    @property
    def stored(self):
        df = pd.concat({b: self.radio[b].stored for b in self.bands})
        df['where'] = 'radio'
        d = {}
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
        super(DtnInductMBLTP, self).initialize(peer, **kwargs)

    def run(self):
        while self.is_alive:
            # Wait until you have received a segment
            segment = yield from self.in_queue.get()

            # Get the session id for this segment
            sid = segment.session_id

            # If a session is not already running and you have never opened a
            # session with this id, do it. The validity of this piece of code
            # hinges on the session ids being sequential and in increasing order
            # as defined in ``DtnAbstractDuctLTP``
            if not self.is_session(sid) and sid > self.last_sid:
                self.initialize_ltp_session(sid)

            # If there is no session opened for this segment, then this segment
            # is for a session that has already ended. Just discard it.
            if not self.is_session(sid): continue

            # Direct the segment to the appropriate ltp_receive process
            # This is either a DS or RA, so no need to put it expedited
            yield from self.ltp_queues[sid].put(segment, 1)

    def initialize_ltp_session(self, session_id):
        # Create a new queue
        self.ltp_queues[session_id] = DtnPriorityQueue(self.env)

        # Initialize the report counter
        self.report_counter[session_id] = 0

        # Increase the last_sid counter
        self.last_sid = max(self.last_sid, session_id)

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
        to_receive     = -1
        received       = set()
        rx_checkpoints = set()
        success        = False  # Ensures you only deliver the blocks once.
        rs             = LtpReportSegment(session_id)
        last_rs        = None

        # Define a function to assess whether you have succeded in transmitting
        # this block. Note that this function has to belong to each ``run_ltp_session``
        # because it will use its variables
        def has_succeeded(success):
            # If you succeeded in the past, then you have not succeeded now
            # This ensures that you only deliver blocks once
            if success: return False

            # If you do not know how much data is in this block, you cannot
            # have succeeded as you have not seen the first checkpoint yet.
            if to_receive == -1: return False

            # You need to have only 1 record in received due to union_intervals
            if len(received) != 1: return False

            # Make sure that the total data volume in the block is the expected
            return sum(c[1] for c in received) >= to_receive

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

                # If in the last RS you did not acknowledge all the data volume
                # in this block, you cannot exit still. Otherwise you will leave
                # the peer induct lingering forever.
                dv_last_rs = sum(c[1] for c in last_rs.claims)
                if dv_last_rs != to_receive: continue

                # At this point you are ready to exit this LTP session
                break

            # If you have succeed, skip these to reduce computational burden
            if not success:
                # Add a reception claim. NOTE: This is different from rfc 5350!!! The offset of
                # the claim is relative to the start of the block, whereas in the spec it is
                # relative to RS' lower bound
                rs.claims.add((segment.offset, segment.length))

                # Compute the received data up until now
                received = self.compute_received_data(rs, received)

            # If you have received all data in the block, you are ready to exit. However, this
            # cannot happen before the first checkpoint because you do not know how long the
            # block is.
            if has_succeeded(success):
                self.deliver_block(session_id)
                success = True

            # If this segment is not a checkpoint, you are done
            if not segment.is_checkpoint: continue

            # If you have already seen this checkpoint, continue. This segment could be a
            # duplicate checkpoint sent by a timer or the second copy through the other band.
            if segment.checkpoint in rx_checkpoints: continue

            # At this point you know that this is a checkpoint and it is not a duplicate.
            # Therefore, add it to set of seen checkpoints
            rx_checkpoints.add(segment.checkpoint)

            # If this is the first time you see a checkpoint, it will tell you the block
            # size. This is only true because of the deferred-ack mode
            if first_checkpt:
                to_receive    = segment.offset + segment.length
                first_checkpt = False

            # This segment is a checkpoint, you must issue a Report Segment in response
            rs.checkpoint = segment.checkpoint
            rs.lower_bnd  = 0
            rs.upper_bnd  = to_receive
            rs.id         = self.new_report_id(session_id)
            rs.claims     = deepcopy(received)              # A copy is necessary!

            # Enqueue the report to be sent
            self.send_through_all(rs)

            # Mark this report segment as pending acknowledgement
            self.pending_ack[session_id][rs.id] = rs

            # Start the timer for the report segment
            self.env.process(self.start_report_timer(session_id, rs.id))

            # If this is the first checkpoint and you have succeeded, then deliver the
            # block because you haven't done so previously. In any other case, you have
            # already delivered the block
            if has_succeeded(success):
                self.deliver_block(session_id)
                success = True

            # Reset the Report Segment
            last_rs = rs
            rs      = LtpReportSegment(session_id)

        # Tear down this LTP session
        self.finalize_ltp_session(session_id)

        #print(self.ltp_sessions)

    def new_report_id(self, session_id):
        # Update the report counter
        self.report_counter[session_id] += 1

        # Return the current value
        return self.report_counter[session_id]

    def compute_received_data(self, rs, received):
        # Append the new claims to the already received data
        received.update(rs.claims)

        # Prepare claims
        offset, length = zip(*received)

        # Transform to numpy arrays
        start = np.array(offset)
        end   = start + np.array(length)

        # Compute the data intervals that these claims acknowledge
        start, end = union_intervals(start, end, stacked=False)

        # Return the new set of received data
        return set(zip(start, end-start))

    def deliver_block(self, session_id):
        # If this block is not present in the peer, it was already delivered
        # This can happen because of the early delivery mechanism of this duct
        if session_id not in self.peer.block: return

        # Get actual block from peer outduct. This does not actually happen,
        # it is just a shortcut for the simulation. Also, you can do this
        # because all connections have propagation delays > 1 second and therefore
        # it is impossible that you have already received the corresponding report
        # acknowledgment
        block = self.peer.block[session_id]

        # UNCOMMENT FOR TESTING
        #self.counter += 1
        #print(self.t, self.counter, 'block delivered for session', session_id)

        # Deliver bundles to the DTN node
        for bundle in block:
            # UNCOMMENT FOR TESTING
            #if bundle.mid in self.delivered:
            #    t2, t1 = self.t, self.delivered[bundle.mid]
            #    dt = t2-t1
            #    print(f'{t1} : Bundle {bundle.mid} already delivered at {t2} - dt={dt}')
            #else: self.delivered[bundle.mid] = self.t
            self.parent.forward(bundle)

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
        self.send_through_all(rs)

        # Start the timer for the report segment
        self.env.process(self.start_report_timer(session_id, rs.id))

    def send_through_all(self, segment):
        """ Send a copy of this segment through all the bands """
        for i, b in enumerate(self.bands):
            s = segment if i == 0 else deepcopy(segment)
            self.radio[b].put(self.neighbor, s, self.peer, self.transmit_mode)

    def __str__(self):
        return "<MBLtpInduct {}-{}>".format(self.parent.nid, self.neighbor)