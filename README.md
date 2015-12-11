COMP112 Project: HTTP Proxy with Cooperative Caching and LFU
Victoria Tang and Allegia Wiryawan

Introduction
The time it takes to download a large file from a web server can get very long, since the HTTP GET request may need to make many hops and travel very far before it reaches the server hosting the desired object. However, if the client application uses a HTTP proxy, then that time can be significantly reduced because the HTTP GET request only needs to reach the proxy and does not have to go all the way to the server if the proxy has cached the object. This is good for overall network traffic because it may also reduce the load and congestion on the network since the client application’s request is served by the proxy which is close to the client. 

If the proxy has cached the content that the client has requested, it serves the request. If it does not have the requested object, then it will go to the web server to retrieve it, thus acting on behalf of the client. Then the proxy will cache the object so that it may serve future requests.

Cooperative caching is when multiple proxies work together to serve client requests. Each proxy has its own cache, but can get assistance from other proxies that it is aware of. Each proxy knows what the other proxies have in their caches. If a proxy has a client’s requested object, then it just serves the request. But if it does not, it can get the object from another proxy, which it knows has the object, and avoid going all the way to the web server.  This will further reduce the probability of an application’s going to the server since there’s more chances that a file is in one of the proxies’ caches.

Our aim was to demonstrate reduced retrieval times when a web browser makes a request for a large web object. We showed this through downloading software. The chance of there being repeated requests for software is small, hence if only a single proxy is used, the application will most likely have to go to the server to retrieve it. But if the software is popular, multiple users will download it and multiple proxies will have it in their cache. Therefore, with cooperative caching, there’ll be very little need for a user to go to the server to download this.

Design & Implementation
Each proxy’s cache will implement a least frequently used (LFU) caching policy; when cache of a proxy is full, it’ll remove the file that was least used.

To implement cooperative caching, proxies will need to know of each other’s host and port to enable connections between them. The proxy will first connect to the bootstrapped proxy (the first active proxy), who will then update the list of proxies and send this updated list to all other active proxies.

Then, when a request is received, proxy will first check its cache. If it’s not present in its cache, it will check its list of bloom filters to see if any of the other proxies have cached the file. By checking the bloom filters instead of connecting to each proxy and asking it for the file, we make our cooperative caching even faster because we cut out the overhead of connecting and pinging all the other proxies. If a bloom filter tells us that a certain proxy has the file, then our proxy will connect to it and request the file. If the we check all of the bloom filters and none of the proxies have the file we want, then we go to the webserver to retrieve the file. We did not have to connect and ping each proxy, only to find that none of them have the file we want. This saves a lot of time. Upon receiving the file from the webserver or another proxy, the proxy will also cache it for future requests.

Thus, the major features of our HTTP proxy are:
LFU eviction policy (if there is a tie in LFU, the earlier file to be cached will be evicted)
Ability for an proxy running on a different IP and port to connect to the boostrapping proxy and announce its arrival
Ability of boostrapping proxy to send out to announce arrival of a new proxy to the other proxies
Ability of each proxy to send its bloom filter data structure to the other proxies
Bloom filters get exchanged once for every two “requests” made in the network
Ability for proxies to check the bloom filters of other proxies and connect to other proxies to make requests if bloom filter indicated that that proxy has probability of having desired file
Bloom filter (from PyBloom) that uses a bit array and hash functions to tell with low-error rates whether a file has been cached by a certain proxy

Challenges
Our first challenge was to become familiar with Python, as we both did not have prior experience in using it.

We had a lot of logistical issues in regards to installing the PyBloom package onto our machines. Furthermore, the lack of documentation on the interface of the bloom filter made it challenging to use. Especially when sending bloom filters over socket, as sockets can only deliver byte streams and not data structures. To achieve this, we had to use the serialization functions of the PyBloom package (fromfile and tofile), and troubles that arise here was ensuring that file pointers were at the correct locations during read and write calls.

Our major logistical issues was that we used threads to allow requests for sites to run concurrently. Because many websites consist of many objects, allowing the proxy to grab them in parallel made it a lot more efficient. However, global variables used in the proxy were not updated quick enough to keep pace with multiple threads. To overcome this, we did most of our testing with curl as it allowed us to grab single objects.