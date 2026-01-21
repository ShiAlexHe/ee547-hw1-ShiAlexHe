Shi He  
shihe@usc.edu  
  
# problem1:  
1. init, send 10 values.  
2. output own values and 10 received values and make sure in order.  
3. workers lock when finish own work till receive message to unlock.   
4. loop 3 & 4 till DONE.  
This strategy should be able to maximize the usage of msg box, and worst case won't be more than n/10.  

# problem2:  
1. follow requirement, complete handler class, use as a logger
2. for each url, use loop to handle run and retry, save reason for each retry

# problem3:  
1. check checksum and duplication
2. if just right next last written, write
3. if smaller than last written, write
4. if buffer have right package, write buffer in order
5. if buffer full, flush
6. if buffer is about full, request for gap

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