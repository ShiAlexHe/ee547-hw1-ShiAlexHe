1. Your buffer size choice and reasoning  
buffer size is given by test function  

2. Your flush strategy (when do you write?)  
flush when: 1. buffer is full 2. buffer have seq right next to last write 3. finalize  

3. Your gap handling approach  
when gap, if not ask for retransmit, when buffer is 80% full, ask for retransmit, if no received when full, ignore

4. Trade-offs you observed during testing
balance the retransmit request and gap. retransmit is decided by buffer size and delay of transition.

