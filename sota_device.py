#!/usr/bin/python

#
# Copyright (C) 2014, Jaguar Land Rover
#
# This program is licensed under the terms and conditions of the
# Mozilla Public License, version 2.0.  The full text of the 
# Mozilla Public License is at https://www.mozilla.org/MPL/2.0/
#
'''
SOTA SERVER CODE: https://gist.github.com/SevenW/47be2f9ab74cac26bf21
The MIT License (MIT)

Copyright (C) 2014, 2015 Seven Watt <info@sevenwatt.com>
<http://www.sevenwatt.com>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

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

from SimpleHTTPServer import SimpleHTTPRequestHandler
import struct
from base64 import b64encode
from hashlib import sha1
from mimetools import Message
from StringIO import StringIO
import errno, socket #for socket exceptions
import json
from subprocess import call
from subprocess import check_output
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer
import ssl

ng_fd = -1
g_package = ''
g_chunk_size = 0
g_total_size = 0
g_chunk_index = 0
g_retry = 0
g_file_name = ''
ws_server = {}

rvi_sota_prefix = "jlr.com/backend/sota"
available_packages = []



class WebSocketError(Exception):
    pass

class HTTPWebSocketsHandler(SimpleHTTPRequestHandler):
    _ws_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    _opcode_continu = 0x0
    _opcode_text = 0x1
    _opcode_binary = 0x2
    _opcode_close = 0x8
    _opcode_ping = 0x9
    _opcode_pong = 0xa

    mutex = threading.Lock()
    
    def on_ws_message(self, message):
        """Override this handler to process incoming websocket messages."""
        pass
        
    def on_ws_connected(self):
        """Override this handler."""
        pass
        
    def on_ws_closed(self):
        """Override this handler."""
        pass
        
    def send_message(self, message):
        self._send_message(self._opcode_text, message)

    def setup(self):
        SimpleHTTPRequestHandler.setup(self)
        self.connected = False
                
    # def finish(self):
        # #needed when wfile is used, or when self.close_connection is not used
        # #
        # #catch errors in SimpleHTTPRequestHandler.finish() after socket disappeared
        # #due to loss of network connection
        # try:
            # SimpleHTTPRequestHandler.finish(self)
        # except (socket.error, TypeError) as err:
            # self.log_message("finish(): Exception: in SimpleHTTPRequestHandler.finish(): %s" % str(err.args))

    # def handle(self):
        # #needed when wfile is used, or when self.close_connection is not used
        # #
        # #catch errors in SimpleHTTPRequestHandler.handle() after socket disappeared
        # #due to loss of network connection
        # try:
            # SimpleHTTPRequestHandler.handle(self)
        # except (socket.error, TypeError) as err:
            # self.log_message("handle(): Exception: in SimpleHTTPRequestHandler.handle(): %s" % str(err.args))

    def checkAuthentication(self):
        auth = self.headers.get('Authorization')
        if auth != "Basic %s" % self.server.auth:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Plugwise"')
            self.end_headers();
            return False
        return True
        
    def do_GET(self):
        if self.server.auth and not self.checkAuthentication():
            return
        if self.headers.get("Upgrade", None) == "websocket":
            self._handshake()
            #This handler is in websocket mode now.
            #do_GET only returns after client close or socket error.
            self._read_messages()
        else:
            SimpleHTTPRequestHandler.do_GET(self)
                          
    def _read_messages(self):
        while self.connected == True:
            try:
                self._read_next_message()
            except (socket.error, WebSocketError), e:
                #websocket content error, time-out or disconnect.
                self.log_message("RCV: Close connection: Socket Error %s" % str(e.args))
                self._ws_close()
            except Exception as err:
                #unexpected error in websocket connection.
                self.log_error("RCV: Exception: in _read_messages: %s" % str(err.args))
                self._ws_close()
        
    def _read_next_message(self):
        #self.rfile.read(n) is blocking.
        #it returns however immediately when the socket is closed.
        try:
            self.opcode = ord(self.rfile.read(1)) & 0x0F
            length = ord(self.rfile.read(1)) & 0x7F
            if length == 126:
                length = struct.unpack(">H", self.rfile.read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self.rfile.read(8))[0]
            masks = [ord(byte) for byte in self.rfile.read(4)]
            decoded = ""
            for char in self.rfile.read(length):
                decoded += chr(ord(char) ^ masks[len(decoded) % 4])
            self._on_message(decoded)
        except (struct.error, TypeError) as e:
            #catch exceptions from ord() and struct.unpack()
            if self.connected:
                raise WebSocketError("Websocket read aborted while listening")
            else:
                #the socket was closed while waiting for input
                self.log_error("RCV: _read_next_message aborted after closed connection")
                pass
        
    def _send_message(self, opcode, message):
        try:
            #use of self.wfile.write gives socket exception after socket is closed. Avoid.
            self.request.send(chr(0x80 + opcode))
            length = len(message)
            if length <= 125:
                self.request.send(chr(length))
            elif length >= 126 and length <= 65535:
                self.request.send(chr(126))
                self.request.send(struct.pack(">H", length))
            else:
                self.request.send(chr(127))
                self.request.send(struct.pack(">Q", length))
            if length > 0:
                self.request.send(message)
        except socket.error, e:
            #websocket content error, time-out or disconnect.
            self.log_message("SND: Close connection: Socket Error %s" % str(e.args))
            self._ws_close()
        except Exception as err:
            #unexpected error in websocket connection.
            self.log_error("SND: Exception: in _send_message: %s" % str(err.args))
            self._ws_close()

    def _handshake(self):
        headers=self.headers
        if headers.get("Upgrade", None) != "websocket":
            return
        key = headers['Sec-WebSocket-Key']
        digest = b64encode(sha1(key + self._ws_GUID).hexdigest().decode('hex'))
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', str(digest))
        self.end_headers()
        self.connected = True
        #self.close_connection = 0
        self.on_ws_connected()
    
    def _ws_close(self):
        #avoid closing a single socket two time for send and receive.
        self.mutex.acquire()
        try:
            if self.connected:
                self.connected = False
                #Terminate BaseHTTPRequestHandler.handle() loop:
                self.close_connection = 1
                #send close and ignore exceptions. An error may already have occurred.
                try: 
                    self._send_close()
                except:
                    pass
                self.on_ws_closed()
            else:
                self.log_message("_ws_close websocket in closed state. Ignore.")
                pass
        finally:
            self.mutex.release()
            
    def _on_message(self, message):
        #self.log_message("_on_message: opcode: %02X msg: %s" % (self.opcode, message))
        
        # close
        if self.opcode == self._opcode_close:
            self.connected = False
            #Terminate BaseHTTPRequestHandler.handle() loop:
            self.close_connection = 1
            try:
                self._send_close()
            except:
                pass
            self.on_ws_closed()
        # ping
        elif self.opcode == self._opcode_ping:
            _send_message(self._opcode_pong, message)
        # pong
        elif self.opcode == self._opcode_pong:
            pass
        # data
        elif (self.opcode == self._opcode_continu or 
                self.opcode == self._opcode_text or 
                self.opcode == self._opcode_binary):
            self.on_ws_message(message)

    def _send_close(self):
        #Dedicated _send_close allows for catch all exception handling
        msg = bytearray()
        msg.append(0x80 + self._opcode_close)
        msg.append(0x00)
        self.request.send(msg)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class WSSOTAHandler(HTTPWebSocketsHandler):
    def on_ws_connected(self):
        self.log_message('%s','websocket connected')

    def on_ws_closed(self):
        self.log_message('%s','websocket closed')
 
    def on_ws_message(self, message):
        global g_fd 
        global g_chunk_index
        global g_chunk_size
        global g_total_size 
        if message is None:
            message = ''

        cmd = json.loads(message)
        tid = cmd['id']

        print "Got message", message
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
    # Change the smack label of the file so that our pkgcmd can access it
    call(["/usr/bin/chsmack", "--access", "System::Shared", g_file_name])
    call(["/usr/bin/sudo", "-u", "app", "/usr/bin/pkgcmd", "-i", "-t", "wgt", "-p", g_file_name, "-q"])

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
    pkg_info = check_output(["/usr/bin/sudo", "-u", "app", "/usr/bin/pkgcmd", "-s", "-t", "wgt", "-p", g_file_name])
    
    line_start = pkg_info.find("pkgid : ")
    line_end = pkg_info.find("\n", line_start)
    pkg_id = pkg_info[line_start+8 : line_end]

    call(["/usr/bin/sudo", "-u", "app", "/usr/bin/pkgcmd", "-k",  "-n", pkg_id, "-q"])
    
    g_retry = 0
    g_package = ''
    g_file_name = ''
    
    
    return {u'status': 0}


def serve_ws():
    global ws_server
    print "Hello"
    while True:
        print "Serving the socket"
        ws_server.serve_forever()
        

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


server = ThreadedHTTPServer(('', 9000), WSSOTAHandler)
server.daemon_threads = True
server.auth = b64encode("")
print('started http server at port 9000')
ws_thread = threading.Thread(target=server.serve_forever)
ws_thread.start()


# ws_thread = threading.Thread(target=ws_server.serve_forever)

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

try:
    while True:
        time.sleep(3600.0)
        
except KeyboardInterrupt:
    print('^C received, shutting down server')
    server.socket.close()
