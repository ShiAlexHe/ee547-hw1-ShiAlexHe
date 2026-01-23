Shi He  
shihe@usc.edu  
  
# problem1
1. Initialize and send 10 values.  
2. Output own values and the 10 received values, and make sure they are in order.  
3. Send another 10 values, and workers lock after finishing their own work until they receive a message to unlock.  
4. Loop steps 3 & 4 until DONE.  

This strategy should be able to maximize the usage of the message box, and in the worst case it will not exceed n/10.

# problem2
1. Follow the requirements, complete the handler class, and use it as a logger.  
2. For each URL, use a loop to handle execution and retries, and save the reason for each retry.

# problem3
1. Check checksum and duplication.  
2. If it is exactly the next packet after the last written one, write it.  
3. If it is smaller than the last written one, write it.  
4. If the buffer has the correct packets, write the buffer in order.  
5. If the buffer is full, flush it.  
6. If the buffer is about n% full, request gap information.  

The choice of n depends on the delay and the balance between request rate and ordering. Since the penalty of unordered packets and requests is unknown, and the delay is also unknown, n is set to 80%.


[//]: # (ee547-hw1-[username]/)

[//]: # (├── problem1/)

[//]: # (│   ├── merge_worker.py)

[//]: # (│   └── README.md)

[//]: # (├── problem2/)

[//]: # (│   ├── http_client.py)

[//]: # (│   └── README.md)

[//]: # (├── problem3/)

[//]: # (│   ├── event_logger.py)

[//]: # (│   └── README.md)

[//]: # (└── README.md)