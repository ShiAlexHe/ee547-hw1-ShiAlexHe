# msg:  
state: TUNLO TDONE FUNLO FDONE (first character 'F' and 'T' is to identify whether already have input in txt file, just for ', ' to split numbers)  
values: 10 values in order that did not output

# phase:  
INIT LOCK UNLOCK DONE  

# strategy:
Each step will send msg, load and save states
1. INIT, send 10 values, lock self; if already have receive values, goto next state. If index reach end, send 'DONE' and set self 'DONE'
2. When receive values and 'unlock' or 'done', unlock self, try output values with this 10 values, make sure in order.Move index to next value and send other 10 values and 'unlock' msg. lock self.
3. continue 2 till all values were sent or output, set self 'DONE' and send 'DONE'.

Send 10 values for each time can maximize the usage of message box.
For each time, this strategy can guarantee output at less 10 values.
Normally when overlap, workers can output it's own data with 10 received values.
When not overlap, worker can take first value as minimal values and output more values till finish or overlap.
