# Victoria Tang and Allegia Wiryawan
# HTTP Proxy with Cooperative Caching and LFU replacement policy

import os,sys,thread,socket,calendar,time,json
from pybloom import BloomFilter

### CONSTANTS ###
CACHE_SIZE = 5
BACKLOG = 5
MAX_DATA_RECV = 999999
TTL = 86400 #seconds
proxy_port = 9301
bootstrap_proxy = '10.4.2.11'  #bootstrapping proxy is always on 10.4.2.11 port 9300


cache = [""] * CACHE_SIZE   # will hold names of our cached files
num_files = 0   # number of files in our cache
bf = BloomFilter(capacity = 50, error_rate = 0.001) #PyBloom by Jay Baird
proxies = [(bootstrap_proxy,proxy_port,bf)]  #master list of other proxies in the network

############################### MAIN PROGRAM ###############################
# Sets up each proxy with its own cache and bloom filter
# Connects to the boostrapping proxy, if needed 
# Periodically triggers exchange of updated bloom filters
# Waits for requests from the client
############################################################################
def main():
    global proxies
    global bf
    
    # check number of arguments
    if (len(sys.argv) < 2):
        print "No port given, using default port 80"
        port = 80
    else:
        port = int(sys.argv[1])

    host = ''
    print "Proxy is running on ", host, ":" , port
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, port))
        s.listen(BACKLOG)

        # All non-bootstrapping proxies will connect to the boostrapping proxy
        # so that they can be added to its master list of proxies

        curr_host = socket.gethostbyname(socket.gethostname())
        # check if the current host is itself the Bootstrapping proxy
        if curr_host != bootstrap_proxy:   

            # serializing the Bloom Filter for storage in a file
            temp_bf = open('temp_bf_send', "w") # create a new file
            bf.tofile(temp_bf)  # serialize the bloom filter and store in in temp_bf file
            temp_bf.close()
            temp_bf = open('temp_bf_send', "r") 

            # create a string so the temp_bf file can be sent over socket connection
            temp2 = ''
            while 1:
                temp = temp_bf.read()
                if len(temp) > 0:
                    temp2 = temp2 + temp
                else:
                    break  
            temp_bf.close()

            if os.path.isfile('temp_bf_send'):  # remove the file used to hold the bloom filter
                os.remove('temp_bf_send')

            # Create the message that a new proxy will use to announce itself to the bootstrapping proxy
            msg_list = ['NEW PROXY\n', curr_host, '\n',str(port),'\n', temp2]
            msg = ''.join(msg_list)
            # connect and send proxy's IP, port, and bloom filter to the bootstrapping proxy
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_sock.connect((bootstrap_proxy,proxy_port))
            temp_sock.send(msg)
            temp_sock.close();

    except socket.error, (value, message):
        if s:
            s.close()
        print "Could not open socket:", message
        sys.exit(1)
    
    count = 1  # used as a indicator of when to exchange updated bloom filters
    while 1:
        conn, cli_addr = s.accept()
        if count % 2 == 0:
            exchange_bloom_filter()
        thread.start_new_thread(execute_request, (conn, cli_addr))
        count = count + 1
    s.close()

#########################################################################
# SENDS other proxies the most recent version of your bloom filter
#########################################################################
def exchange_bloom_filter():
        global bf
        if len(proxies) < 2: 
            print "ONLY ONE PROXY IN NETWORK"  # so do not exchange bloom filters
            return

        # serializing the bloom filter for file storage
        temp_bf = open('temp_bf_send', "w")  # create a new file
        bf.tofile(temp_bf)
        temp_bf.close()
        temp_bf = open('temp_bf_send', "r")

        # creating a string so the file can be sent over socket connection
        temp2 = ''
        while 1:
            temp = temp_bf.read()
            #print "Reading from file: ", len(temp)
            if len(temp) > 0:
                temp2 = temp2 + temp
            else:
                break
        temp_bf.close()

        if os.path.isfile('temp_bf_send'): # remove the file used to hold the bloom filter
            os.remove('temp_bf_send')

        curr_host = socket.gethostbyname(socket.gethostname())
        # create a new message to send the most recent bloom filter
        new_msg = ['UPDATE BF\n', curr_host, '\n', temp2]  
        to_send = ''.join(new_msg)
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for proxy in proxies:  # send the message to all proxies in the network
            if proxy[0] != curr_host:
                temp_sock.connect((proxy[0],proxy[1]))
                temp_sock.send(to_send)
        temp_sock.close()
  
#######################################################################
# Parses a string so that it can be formatted into a list of tuples
# Tuple: (IP, port, bloom filter)
#######################################################################
def convert_string_to_list(temp_buff):
    global proxies
    temp_list = temp_buff.split('\n') # break up the string at each \n
    proxies = []  
    size = len(temp_list)

    # create a list of proxies with the special tuple
    i = 1;
    while i < size:
        temp_bf_read = open('bf_read', "w") # create new file bf_read
        temp_bf_read.write(temp_list[i+2])  # write the bloom filter to the file
        temp_bf_read.write('\n')
        temp_bf_read.write(temp_list[i+3])
        temp_bf_read.close()
        temp_bf_read = open('bf_read', "r") 
        temp_bf = BloomFilter.fromfile(temp_bf_read) # de-serialize the bloom filter
        # add the tuple to the list of proxies
        proxies.append((temp_list[i], int(temp_list[i+1]), temp_bf))
        i = i + 4 

        if os.path.isfile('bf_read'): # remove the file used to hold the bloom filter
            os.remove('bf_read')
    #print "UPDATED PROXIES"
    #print proxies

######################################################################
# RECIEVES updated bloom filters from other proxies
######################################################################
def update_bf(request):
    global proxies
    temp_list = request.split('\n')
    #print temp_list
    updated_proxy = temp_list[1] # ip of other proxy
    # write the bloom filter to a file bf_upd
    temp_bf_recv = open('bf_upd', "w") 
    temp_bf_recv.write(temp_list[2])
    temp_bf_recv.write('\n')
    temp_bf_recv.write(temp_list[3])
    temp_bf_recv.close()
    temp_bf_recv = open('bf_upd', 'r')
    # de-serialize the bloom filter
    temp_bf = BloomFilter.fromfile(temp_bf_recv)
    temp_bf_recv.close()

    if os.path.isfile('bf_upd'): # remove the file used to hold the bloom filter
        os.remove('bf_upd')

    index = 0;
    for proxy in proxies: 
        if proxy[0] == updated_proxy: # update only the proxy who's bloom filter is updated
            print "UPDATING BF OF PROXY: ", proxy[0]
            curr_port = proxy[1]
            break
        index = index + 1
    proxies[index] = (updated_proxy, curr_port, temp_bf) # update entry in the list

########################################################################
# Checks what kind of request is coming in
# Handles lists of proxies, updating bloom filter list, and adding a new proxy
########################################################################
def execute_request(conn, cli_addr):
    global cache
    global num_files
    #print "EXECUTE REQUEST CLIENT ADDRESS: ", cli_addr
    
    request = conn.recv(MAX_DATA_RECV)

    # handle requests
    if request.find('NEW PROXY') > -1: # add the proxy to the proxy list, if needed
        add_proxy(request, conn)
    elif request.find('NEW LIST OF PROXIES') > -1: # receive an updated proxy list
        convert_string_to_list(request)
    elif request.find('UPDATE BF') > -1:  # update the bloom filters
        update_bf(request)
    else:  # check if the request is from another proxy (versus a client)
        is_proxy = False
        is_proxy = check_proxies(cli_addr)
        if is_proxy == True: 
            handle_proxy_request(request, conn, cli_addr)
        else:
            handle_web_request(request, conn, cli_addr) 

#####################################################################
# Add a new proxy to the proxies list
#####################################################################
def add_proxy(request, conn):
    global proxies
    recv_list = request.split('\n')
    #print "RECV LIST: ",recv_list
    new_proxy = recv_list[1]
    new_port = int(recv_list[2])
    temp_bf = open("temp_bf_rec", "w+") # write the bloom filter string to a file
    temp_bf.write(recv_list[3])
    temp_bf.write('\n');
    temp_bf.write(recv_list[4])
    temp_bf.close()
    temp_bf = open("temp_bf_rec", 'r')
    new_bf = BloomFilter.fromfile(temp_bf)     # de-serialize the bloom filter
    temp_bf.close()

    if os.path.isfile('temp_bf_rec'): # remove the temp file
        os.remove('temp_bf_rec')
    print "GOT BLOOM FILTER"

    proxies.append((new_proxy,new_port,new_bf))
    #print "NEW PROXIES: ",proxies
    temp_list = ['NEW LIST OF PROXIES']
    for proxy in proxies:
        temp_list.append('\n')
        temp_list.append(proxy[0]) # add IP
        temp_list.append('\n')
        temp_list.append(str(proxy[1])) # add port
        temp_list.append('\n')
        temp_bf = open('temp_bf_send', "w") # serialize the bloom filter for sending
        proxy[2].tofile(temp_bf)
        temp_bf.close()
        temp_bf = open('temp_bf_send', "r")

        # create the a string so the bloom filter can be sent over socket connect
        temp2 = ''
        while 1:
            temp = temp_bf.read()
            #print "Reading from file: ", len(temp)
            if len(temp) > 0:
                temp2 = temp2 + temp
            else:
                break

        temp_bf.close()
        temp_list.append(temp2)  # add bloom filter   

    if os.path.isfile('temp_bf_send'): # remove temp file
        os.remove('temp_bf_send')

    #print temp_list
    temp_string = ''.join(temp_list) # create a string representation of the list

    for proxy in proxies:
        if proxy[0] != bootstrap_proxy: #only bootstrapping proxy will do this
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_sock.connect((proxy[0],proxy[1])) # connect to each proxy and send the new list of proxies
            temp_sock.send(temp_string)
            temp_sock.close()

#########################################################################
# Checks if client is another proxy
#########################################################################
def check_proxies(cli_addr):
    #print "CHECK IF CLILENT IS PROXY"
    curr_host = socket.gethostbyname(socket.gethostname())
    for proxy in proxies:
        if cli_addr[0] == proxy[0] and cli_addr[0] != curr_host:
            print "CLIENT IS PROXY AND NOT ITSELF!"
            return True
    return False

#########################################################################
# Send a file to another proxy if you have the desired file
# request is the file name
#########################################################################
def handle_proxy_request(request, conn, cli_addr):
    print "HANDLING REQUEST FROM FELLOW PROXY REQUEST"
    print request
    if os.path.isfile(request):   # have the file cached
        print "I HAVE REQUESTED FILE: ", request
        cache_file = open(request, "r")
        time_acc = cache_file.readline() # get the timestamp
        num_acc = cache_file.readline()  # get the number of times the files was accessed
        
        # send the entire file 
        while 1: 
            data = cache_file.read()
            if len(data) != 0:
                conn.send(data)
            else:
                conn.send("DONE SENDING")
                break
    else:
        print "FILE'S NOT HERE"
        conn.send("FILE'S NOT HERE")
    #conn.close()
    return

#########################################################################
# Goes to the webserver to server the request
#########################################################################         
def handle_web_request(request, conn, cli_addr):
    global bf
    global num_files
    global cache

    first_line = request.split('\n')[0] # get the first line of HTTP GET request
    if first_line == '':
        return
    else:
        url = first_line.split(' ')[1] #get the url

    #get the name of the webserver
    http_pos = url.find("://")
    if http_pos == -1:
        temp = url
    else:
        temp = url[(http_pos+3):] # 3 = ://, get the rest of the url

    port_pos = temp.find(":") # port is specified after :
    web_pos = temp.find("/") # web_pos is the end of the webserver name
    if web_pos == -1:
        web_pos = len(temp) #the webserver is the entire url

    webserver = ""
    port = -1
    if (port_pos == -1 or web_pos < port_pos):
        # if port is not given or is after the webserver name...invalid
        port = 80 #use default http port
        webserver = temp[0:web_pos] 
    else:
        port = int((temp[(port_pos + 1):])[:web_pos - port_pos - 1])
        # get the part in between : and /
        # for example, comp112-01.cs.tufts.edu:9300/about.html
        webserver = temp[0:port_pos]

    try:
        access_time = calendar.timegm(time.gmtime()) # the time we want the file
        in_cache = True # assume in cache
        file_name = url.replace(":", "").replace("\\", "").replace("?","").replace("/", "").replace("HTTP", "").replace("http", "").replace("|", "")
        file_name = file_name[0:255] # max length of file name is 255
        print "filename is: ", file_name

        if os.path.isfile(file_name): #file IS in the cache
            print "IN CACHE"
            cache_file = open(file_name, "r")
            data = cache_file.readline()
            cache_file_time = int(data)
            data = cache_file.readline()
            file_accesses = int(data)  # num of times the file has been requested/accessed
            #print "file_name: ", file_name, "has file_accesses: ", file_accesses
            file_accesses = file_accesses + 1

            if access_time - cache_file_time > TTL: # if exceed TTL (file is older the 24 hours)
                cache_file = open(file_name, "w+") # erase cached file contents
                cache_file.write(repr(access_time)) # update with current time
                cache_file.write('\n')
                cache_file.write(repr(file_accesses))  # keep the file accesses
                cache_file.write('\n')
                cache_file.close()
                in_cache = False  # file is outdated, so it is no longer in the cache
            else: # we can still use the same file that is cached because it is recent enough
                print "UPDATING ACCESS & REWRITE"
                data = cache_file.read() 
                cache_file = open(file_name, "w+")
                cache_file.write(repr(cache_file_time)) # write the time the file was cached
                cache_file.write('\n')
                cache_file.write(repr(file_accesses)) # write the number of times it was accessed
                cache_file.write('\n')
                cache_file.write(data) # write the object data to the file
                cache_file.close()        

        else: # file is NOT in the cache
            print "NOT IN CACHE"
            in_cache = False
            if num_files < CACHE_SIZE:  # cache is not full yet
                cache[num_files] = file_name  # add the file to the cache
                num_files = num_files + 1
            else: # cache is full and we need to discard the least frequently used file
                lfu_file, lfu_index = least_used(cache)
                if os.path.isfile(lfu_file):
                    os.remove(lfu_file)
                    print "REMOVED: ", lfu_file, " AT INDEX: ", lfu_index
                cache[lfu_index] = file_name
                num_files = CACHE_SIZE 
            cache_file = open(file_name, "w+") # create new file in cache
            cache_file.write(repr(access_time)) # record the access time
            cache_file.write('\n')
            cache_file.write("1\n") #file access = 1 bc this is the first time is has been requested
            
        if in_cache == False: # not in the cache
            get_data = True
            curr_host = socket.gethostbyname(socket.gethostname())
            bf.add(file_name)
            # check the bloom filters of other proxies and see if they have the desired file
            for proxy in proxies:
                print "CHECK PROXY: ", proxy[0], " BF CONTAINS: ", proxy[2].__contains__(file_name), "file: ", file_name
                if curr_host != proxy[0] and proxy[2].__contains__(file_name): # if the proxy has cached the file
                    proxserv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    proxserv_socket.connect((proxy[0],proxy[1]))  # connect to that proxy to get that file
                    
                    while 1:  # send data to the client
                        proxserv_socket.send(file_name)
                        data = proxserv_socket.recv(MAX_DATA_RECV)
                        #print "Data received: ", data
                        if data.find("FILE'S NOT HERE") > 0 or data.find("DONE SENDING") > 0:
                            break
                        print "DATA IS IN PROXY: ", proxy, " File: ", file_name
                        cache_file = open(file_name, "a+")
                        cache_file.write(data)
                        cache_file.close()
                        conn.send(data)
                        get_data = False #data has been sent, no need to go to webserver
                    proxserv_socket.close()

            if get_data == False:
                len_time = calendar.timegm(time.gmtime()) - access_time
                print "File: ", file_name
                #print "Time taken to get file from other proxy: ", len_time
            if get_data == True:
                #go to webserver and get data
                print "GOING TO WEBSERVER: ", webserver
                proxserv_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                proxserv_socket.connect((webserver,port))
                #print "CONNECTED TO WEBSERVER" 
                proxserv_socket.send(request)
                #print "SENT REQUEST: ", request

                # write the data to a file    
                while 1:
                    #print "BEFORE RECV!!!!"
                    data = proxserv_socket.recv(MAX_DATA_RECV)
                    #print "GETTING IT FROM WEBSERVER"
                    if(len(data) > 0):
                        cache_file = open(file_name, "a+")
                        cache_file.write(data)
                        #print "WROTE IT TO CACHE FILE"
                        cache_file.close()
                        #print "CLOSED CACHE FILE"
                        #send data to client
                        conn.send(data)
                        #print "SENT IT TO CLIENT"
                    #if(len(data) < MAX_DATA_RECV):
                    #   break
                    else:
                        #print "NO MORE DATA BEING RECEIVED"
                        break
                #print "EXITTED WHILE"
                proxserv_socket.close() #close connection to webserver
                len_time = calendar.timegm(time.gmtime()) - access_time
                print "File: ", file_name,  " Time taken to get file from webserver: ", len_time
        else: # in the cache
            print "SENDING FROM CACHE"
            cache_file = open(file_name, "r")
            time_acc = cache_file.readline() # get the time
            num_acc = cache_file.readline()  # get the number of accesses
            while 1:    # send the file 
                data = cache_file.read()
                if len(data) != 0:
                    conn.send(data)
                else:
                    break
            len_time = calendar.timegm(time.gmtime()) - access_time
            print "File: ", file_name, " Time taken to get file from cache: ", len_time
        conn.close()
        #print "I SENT IT :)"
        #print "NUMBER OF FILES IN CACHE: ", num_files
    except socket.error, (value, message):
        if proxserv_socket:
            proxserv_socket.close()
        if conn:
            conn.close()
        print "peer reset ", value
        print message
        sys.exit(1)

#########################################################################
# Determine the file in the cache with the lowest number of accesses
#########################################################################
def least_used(cache):
    #print "IN LEAST_USED" 
    i = 0
    name = cache[0] #name of first file in cache
    #print "HELLO2, name: ", name
    index = 0
    #curr_file = open(name, "r")
    #time = curr_file.readline()
    min_access = 999999 #number of accesses of first file
    #curr_file.close()
    for curr_name in cache:
        #print "HELLO3, curr_name: ", curr_name
        curr_file = open(curr_name, "r")
        data = curr_file.readline()
        time = data
        data = curr_file.readline()
        curr_access = data
        if curr_access < min_access:
            min_access = curr_access
            name = curr_name
            index = i
        i = i + 1
    print "Least frequently used is: ", name
    return name, index

#########################################################################
if __name__ == '__main__':
    main()
