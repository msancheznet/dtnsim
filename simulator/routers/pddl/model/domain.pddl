(define (domain DTN_Data_Routing_v4)
    (:requirements :typing :fluents :negative-preconditions :equality :durative-actions :timed-initial-literals)
    (:types
      Data - object
      Agent - object
    )
    (:predicates
      (connected ?age - Agent ?age1 - Agent)
      (at ?dat - Data ?age - Agent)
      (idle ?age - Agent)
    )
    (:functions
      (size ?dat - Data)
      (energy_usage_tx ?age - Agent)
      (battery_capacity ?age - Agent)
      (battery_level ?age - Agent)
      (energy_usage_rx ?age - Agent)
      (bandwidth ?from - Agent ?to - Agent)
      (total_energy)
      (energy_left_penalty)
      (bandwidth_threshold)
    )
    (:durative-action transfer
     :parameters (?self - Agent ?target - Agent ?data - Data)
     :duration (= ?duration (* (size ?data) (bandwidth ?self ?target)))
     :condition
       (and
         (at start (at ?data ?self))
         (at start (not (= ?self ?target)))
         (at start (connected ?self ?target))
         (over all (connected ?self ?target))
         (at start (idle ?self))
         (at start (> (battery_level ?self) (* (energy_usage_tx ?self) (* (size ?data) (bandwidth ?self ?target)))))
         (at start (> (battery_level ?target) (* (energy_usage_rx ?target) (* (size ?data) (bandwidth ?self ?target)))))
         (at start (<= (bandwidth ?self ?target) (bandwidth_threshold)))
         (at start (> (bandwidth ?self ?target) 0))
       )
     :effect
       (and
         (at start (not (at ?data ?self)))
         (at end (at ?data ?target))
         (at start (not (idle ?self)))
         (at end (idle ?self))
         (at start (decrease (battery_level ?self) (* (energy_usage_tx ?self) (* (size ?data) (bandwidth ?self ?target)))))
         (at start (decrease (battery_level ?target) (* (energy_usage_rx ?target) (* (size ?data) (bandwidth ?self ?target)))))
         (at start (increase (energy_left_penalty) (- (battery_capacity ?target) (battery_level ?target))))
         (at start (increase (total_energy) (* (+ (energy_usage_tx ?self) (energy_usage_rx ?target)) (* (size ?data) (bandwidth ?self ?target)))))
       )
    )

)
