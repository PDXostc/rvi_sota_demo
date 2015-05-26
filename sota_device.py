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
from subprocess import call
from subprocess import check_output

ng_fd = -1
g_package = ''
g_chunk_size = 0
g_total_size = 0
g_chunk_index = 0
g_retry = 0
g_file_name = ''

rvi_sota_prefix = "jlr.com/backend/sota"
available_packages = []

class WebSocketsHandler(SocketServer.StreamRequestHandler):
    magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
 
    def setup(self):
        SocketServer.StreamRequestHandler.setup(self)
        print "connection established", self.client_address
        self.handshake_done = False
 
    def handle(self):
        print "Handle"
        self.active = True
        while self.active:
            if not self.handshake_done:
                self.handshake()
            else:
                self.read_next_message()
 
    def read_next_message(self):
        msg = self.rfile.read(2)
        if len(msg) < 2:
            print "Connection closed"
            self.active = False
            return 

        length = ord(msg[1]) & 127
        if length == 126:
            length = struct.unpack(">H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self.rfile.read(8))[0]
        masks = [ord(byte) for byte in self.rfile.read(4)]
        decoded = ""
        for char in self.rfile.read(length):
            decoded += chr(ord(char) ^ masks[len(decoded) % 4])
        self.on_message(decoded)
 
    def send_message(self, message):
        self.request.send(chr(129))
        length = len(message)
        if length <= 125:
            self.request.send(chr(length))
        elif length >= 126 and length <= 65535:
            self.request.send(chr(126))
            self.request.send(struct.pack(">H", length))
        else:
            self.request.send(chr(127))
            self.request.send(struct.pack(">Q", length))
        self.request.send(message)
 
    def handshake(self):
        data = self.request.recv(1024).strip()
        headers = Message(StringIO(data.split('\r\n', 1)[1]))
        if headers.get("Upgrade", None) != "websocket":
            return
        print 'Handshaking...'
        key = headers['Sec-WebSocket-Key']
        digest = b64encode(sha1(key + self.magic).hexdigest().decode('hex'))
        response = 'HTTP/1.1 101 Switching Protocols\r\n'
        response += 'Upgrade: websocket\r\n'
        response += 'Connection: Upgrade\r\n'
        response += 'Sec-WebSocket-Accept: %s\r\n\r\n' % digest
        self.handshake_done = self.request.send(response)
    

    def on_message(self, message):
        global g_fd 
        global g_chunk_index
        global g_chunk_size
        global g_total_size 
        cmd = json.loads(message)
        tid = cmd['id']

        if cmd['method'] == 'GetPendingUpdates':
            self._get_pending_updates(cmd['id'])
            return
            
        if cmd['method'] == 'StartUpdate':
            print "Got StartUpdate"
            self._start_update(cmd['id'])
            self.send_message(json.dumps({'jsonrpc': '2.0',
                                          'id': tid,
                                          'result': "" }))
            return 

        if cmd['method'] == 'CancelUpdate':
            print "Got CancelUpdate"
            self._cancel_download()
            self.send_message(json.dumps({'jsonrpc': '2.0',
                                          'id': tid,
                                          'result': "" }))
            return 

        if cmd['method'] == 'GetCarSyncState':
            # Check if we have closed the given file.
            # If so, return state idle to shut down progress bar
            # in HMI.
            if g_fd == -1:
                self.send_message(json.dumps({'jsonrpc': '2.0',
                                              'id': tid,
                                              'result': { 'progress': 100, 
                                                          'state': 'Idle'} }))
                return

        
            if g_chunk_size != 0:
                index = int(float(g_chunk_index) * (float(g_chunk_size)/ float(g_total_size)) * 100.0)
            else:
                index = 0

            self.send_message(json.dumps({'jsonrpc': '2.0',
                                          'id': tid,
                                          'result': { 'progress': index, 
                                                      'state': 'Update'} }))
            # Change 'state' to Idle when done
    
            return
        print "UNKNOWN MESSAGE", message
        return 

        
    def _cancel_download(self):
        pkg = available_packages.pop(0)
        retry = pkg['retry']

        print "Will cancel download of package:",pkg['uuid']
        rvi_server.message(service_name = rvi_sota_prefix + "/cancel_download",
                           timeout = int(time.time())+60,
                           parameters = [{ 
                               u'retry': retry
                           }])
        return

    def _start_update(self, tid):
        global full_notify_service_name
        global g_retry
        global g_package
        global g_fd
        global g_chunk_index
        # Strip the last component off self's full notify
        # service name to get a destination to send over
        # to the SOTA server's initiate_download

        last_slash = full_notify_service_name.rfind('/')
        destination = full_notify_service_name[:last_slash]

        self.send_message(json.dumps({'jsonrpc': '2.0',
                                      'id': tid,
                                      'result': [ ] }))

        pkg = available_packages.pop(0)
        package = pkg['uuid']
        g_retry = pkg['retry']
        g_fd = 1
        g_chunk_index = 0
        g_package = package
        print "Will initate download of package: {} ({})".format(package, rvi_sota_prefix + "/initiate_download"),
        rvi_server.message(service_name = rvi_sota_prefix + "/initiate_download",
                           timeout = int(time.time())+60,
                           parameters = [{ 
                               u'package': package,
                               u'retry': g_retry,
                               u'destination': destination
                           }])

        return

    def _get_pending_updates(self, tid):
        global available_packages
        print "Available Packages:", available_packages
        result = { 
            'jsonrpc': '2.0',
            'id': tid,
            'result': available_packages
        }
        self.send_message(json.dumps(result))


def usage():
    print "Usage:", sys.argv[0], "<rvi_url> <service_id>"
    print "  <rvi_url>         URL of  Service Edge on a local RVI node"
    print
    print "The RVI Service Edge URL can be found in"
    print "[backend,vehicle].config as"
    print "env -> rvi -> components -> service_edge -> url"
    print
    print "The Service Edge URL is also logged as a notice when the"
    print "RVI node is started."
    sys.exit(255)

 
def notify(package, retry):
    print "Available packet:", package
    global rvi_server
    available_packages.append({
        "uuid": package,
        "retry": retry,
            "version": {
                "version_major":1,
                "version_minor":0,
                "version_build":0
            }
        })

    return {u'status': 0}

def start(package, chunk_size, total_size):
    global g_fd
    global g_package
    global g_chunk_size
    global g_total_size
    global g_file_name
    

    g_package = package
    g_chunk_size = chunk_size
    g_total_size = total_size
    g_file_name = "/tmp/" + package.replace(" ", "_") + ".wgt"

    print "Starting package:", g_file_name
    
    try: 
        os.remove(g_file_name)
    except:
        print "File {} does not exist, which is good".format(g_file_name)


    g_fd = open(g_file_name, "w")
    return {u'status': 0}

def chunk(index, msg):
    global g_fd
    global g_chunk_size
    global g_chunk_index
    
    g_chunk_index = index
    decoded_msg  = base64.b64decode(msg)

    print "Chunk:", index, " ck_sz:", g_chunk_size, " msg_sz:", len(decoded_msg), " offset:", g_chunk_index * g_chunk_size

    g_fd.seek(g_chunk_index * g_chunk_size)
    g_fd.write(decoded_msg)
    return {u'status': 0}


def finish(dummy):
    global g_fd
    global g_retry
    global g_package
    global g_chunk_index
    global g_file_name

    print "Package:", g_package, " is complete in ", g_file_name
    if g_fd != -1:
        print "Closing", g_fd
        g_fd.close()

    g_fd = -1
    g_chunk_index = 0
    call(["/usr/bin/pkgcmd", "-i", "-t", "wgt", "-p", g_file_name, "-q"])

    print "Package:", g_package, " installed"

    # Send a completion message to the SOTA server

    rvi_server.message(service_name = rvi_sota_prefix + "/download_complete",
                       timeout = int(time.time())+60,
                       parameters = [{ 
                           u'status': 0,
                           u'retry': g_retry
                       }])

    # Kill any executing instances oif the package we just upgraded.


    # Extract the package id by running a status on the file we just installed
    # and extract the 
    #   pkgid : JLRPOCX016
    # line from the result
    pkg_info = check_output(["/usr/bin/pkgcmd", "-s", "-t", "wgt", "-p", g_file_name])
    
    line_start = pkg_info.find("pkgid : ")
    line_end = pkg_info.find("\n", line_start)
    pkg_id = pkg_info[line_start+8 : line_end]

    call(["/usr/bin/pkgcmd", "-k",  "-n", pkg_id, "-q"])
    
    g_retry = 0
    g_package = ''
    g_file_name = ''
    
    
    return {u'status': 0}



# 
# Check that we have the correct arguments
#
if len(sys.argv) != 2:
    usage()

# Grab the URL to use
[ progname, rvi_url ] = sys.argv    


# setup the service names we will register with
# The complete service name will be: 
#  jlr.com/vin/1234/hvac/publish
#       - and -
#  jlr.com/vin/1234/hvac/subscribe
#
# Replace 1234 with the VIN number setup in the
# node_service_prefix entry in vehicle.config

# Setup an outbound JSON-RPC connection to the RVI Service Edge.
# Setup a connection to the local RVI node
rvi_server = RVI(rvi_url)
rvi_server.start_serve_thread() 


# Register our service  and invoke 'service_invoked' if we 
# get an incoming JSON-RPC call to it from the RVI node
#




# Setup a websocket thread
ws_server = SocketServer.TCPServer(("", 9000), WebSocketsHandler)
ws_server.allow_reuse_address = True
ws_thread = threading.Thread(target=ws_server.serve_forever)
ws_thread.start()

# We may see traffic immediately from the RVI node when
# we register. Let's sleep for a bit to allow the emulator service
# thread to get up to speed.
time.sleep(0.5)

# Repeat registration until we succeeed
rvi_dead = True

while rvi_dead:
    try: 
        full_notify_service_name = rvi_server.register_service("/sota/notify", notify )
        rvi_dead = False
    except:
        print "No rvi. Wait and retry: ",  full_notify_service_name
        time.sleep(2.0)

full_start_service_name = rvi_server.register_service("/sota/start", start )
full_chunk_service_name = rvi_server.register_service("/sota/chunk", chunk )
full_finish_service_name = rvi_server.register_service("/sota/finish", finish )


print "SOTA Client"
print "Vehicle RVI node URL:       ", rvi_url
print "Full notify service name :  ", full_notify_service_name
print "Full start service name  :  ", full_start_service_name
print "Full chunk service name  :  ", full_chunk_service_name
print "Full finish service name :  ", full_finish_service_name

while True:
    time.sleep(3600.0)
