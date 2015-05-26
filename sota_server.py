#!/usr/bin/python

#
# Copyright (C) 2014, Jaguar Land Rover
#
# This program is licensed under the terms and conditions of the
# Mozilla Public License, version 2.0.  The full text of the 
# Mozilla Public License is at https://www.mozilla.org/MPL/2.0/
#

#
# Simple SOTA Client
#
import sys
from rvilib import RVI
import jsonrpclib
import random
import time
import threading
import os
import base64
import struct
import SocketServer
from base64 import b64encode
from hashlib import sha1
from mimetools import Message
from StringIO import StringIO
import json
import Queue
        
transaction_id = 0
package_queue = Queue.Queue()

def package_pusher():
    global package_queue
    global transaction_id

    while True:
        [package, destination] = package_queue.get()
        print "Package pushed will push",package,"to",destination
        try:
            f = open(package)

        except Err:
            print "Could not open",file_name,":", Err
            return
        

        chunk_size = 128*1024

        f_stat = os.stat(package)
    
        transaction_id += 1
        rvi_server.message(service_name = destination + "/start",
                           timeout = int(time.time())+60,
                           parameters = [{ u'package': package, 
                                           u'chunk_size': chunk_size,
                                           u'total_size': f_stat.st_size
                                       }])

        index = 0

        while True:
            offset = f.tell()
            msg =  f.read(chunk_size) 
            if msg == "":
                break

            print "Sending package:", package, " chunk:", index, " offset:", offset, " message size: ", len(msg)

            transaction_id+=1
            rvi_server.message(service_name = destination + "/chunk",
                               timeout = int(time.time())+60,
                               parameters = [
                                   { u'index': index }, 
                                   { u'msg': base64.b64encode(msg) }])
            
            index += 1

        f.close()
        print "Finishing package:", package
        time.sleep(1.0)

        transaction_id+=1
        rvi_server.message(service_name = destination + "/finish",
                           timeout = int(time.time())+60,
                           parameters = [ { u'dummy': 0}])

def usage():
    print "Usage:", sys.argv[0], "<rvi_url>"
    print "  <rvi_url>         URL of  Service Edge on a local RVI node"
    print
    print "The RVI Service Edge URL can be found in"
    print "[backend,vehicle].config as"
    print "env -> rvi -> components -> service_edge -> url"
    print
    print "The Service Edge URL is also logged as a notice when the"
    print "RVI node is started."
    sys.exit(255)
        
 
def initiate_download(package, retry, destination):
    print "Will push packet", package, " transaction id", retry, " to",destination
    package_queue.put([package, destination])
    return {u'status': 0}

def cancel_download(retry):
    print "transaction", retry, "was cancelled by device."
    return {u'status': 0}

def download_complete(status, retry):
    print "Download transaction",retry," completed with:",status
    return {u'status': 0}


# 
# Check that we have the correct arguments
#
if len(sys.argv) != 2:

    usage()

# Grab the URL to use
[ progname, rvi_url ] = sys.argv    

# Setup an outbound JSON-RPC connection to the RVI Service Edge.
rvi_server = RVI(rvi_url)
rvi_server.start_serve_thread() 

#
# Regsiter callbacks for incoming JSON-RPC calls delivered to
# the SOTA server from the vehicle RVI node's Service Edge.
#

full_initiate_download_service_name = rvi_server.register_service("/sota/initiate_download", initiate_download )
full_cancel_download_service_name = rvi_server.register_service("/sota/cancel_download", cancel_download )
full_download_complete_service_name = rvi_server.register_service("/sota/download_complete", download_complete )


print "Vehicle RVI node URL:                 ", rvi_url
print "Full initiate download service name : ", full_initiate_download_service_name
print "Full download complete service name : ", full_download_complete_service_name
print "Full cancel download service name   : ", full_cancel_download_service_name

chunk_size = 1024*64

#
# Start the queue dispatcher thread
#
package_pusher_thr = threading.Thread(target=package_pusher)
package_pusher_thr.start()

while True:
    transaction_id += 1
    line = raw_input('Enter <vin> <file_name> or "q" for quit: ')
    if line == 'q':
        rvi_server.shutdown()
        sys.exit(0)

    
        
    # Read a line and split it into a key val pair
    lst = line.split(' ')
    if len(lst) != 2:
        print "Nope", len(lst), lst
        continue
    
    [vin, file_name] = line.split(' ')
    dst = 'jlr.com/vin/'+vin+'/sota'
    try:
        f = open(file_name)
    except Err:
        print "Could not open",file_name,":", Err
        continue
    
    rvi_server.message(service_name = dst + "/notify",
                       timeout = int(time.time())+60,
                       parameters = [{ u'package': file_name,
                                       u'retry': transaction_id }])

    print "Queueing package ", file_name, " to ", dst
    package_queue.put([file_name, dst])

    print('Package {} sent to {}'. format(file_name, dst))
