#!env python
import calendar
import json
import lxml.html
import md5
import os
import re
import shelve
import string
import struct
import tempfile
import time
import urllib

import M2Crypto
import StringIO

import pycurl
import tornado.autoreload
import tornado.ioloop
import tornado.options
import tornado.web as web

# Pseudo Session
class PseudoSession(object):
    """
    A persistantly storage backed dictionary which encapsulates the config for
    a pycurl session, the actual I/O, and the responses
    """
    def __init__(self, psid, req=None):
        self.psid = psid        

        ssn_store = os.path.join(tempfile.gettempdir(), psid)
        if req is None:
            self._store = shelve.open(ssn_store, writeback=True)
        else:
            self._store = shelve.open(ssn_store, flag='n', writeback=True)
            x = req.get_query_arguments('o_doipv6')
            self._store['cfg'] = {
                'base_url': req.get_query_argument('url'),
                'h_useragent': req.get_query_argument('h_useragent'),
                'doipv6': True if len(x) else False
            }

            self.unbuffer()
            self._store.sync()

    def buffer(self):
        self._store['buffers'].append({
            'header': '',
            'headers': {},
            'body': '',
            'debug': [],
            'cert_chain': [],
            'psid': self.psid,
            'url': '',
        })
        self.buf = self._store['buffers'][-1]
        self.cfg = self._store['cfg']

    def unbuffer(self):
        self._store['buffers'] = []

    def get(self, url):
        self.buf['url'] = url

        c = pycurl.Curl()
        c.setopt(c.URL, url)
        #c.setopt(c.USERAGENT, self.cfg.h_useragent)

        c.setopt(c.HEADER, False) # do not include the header in the body output
        c.setopt(c.FORBID_REUSE, True)
        c.setopt(c.NOPROGRESS, True)
        c.setopt(c.TIMEOUT_MS, 5000)
        c.setopt(c.VERBOSE, True)

        if self.cfg['doipv6']:
            c.setopt(c.IPRESOLVE, c.IPRESOLVE_V6)

        # DNS_SERVERS
        # USE_SSL

        # SSL_VERIFYPEER, False
        c.setopt(c.SSL_VERIFYPEER, False)

        # setup the callbacks
        c.setopt(c.DEBUGFUNCTION, self.curl_debug)
        c.setopt(c.HEADERFUNCTION, self.curl_header)
        c.setopt(c.WRITEFUNCTION, self.curl_write)

        c.perform()

    def curl_debug(self, debug_type, debug_message):
        if debug_type == pycurl.INFOTYPE_SSL_DATA_IN:
            #print "debug(%d): %d" % (debug_type, len(debug_message))
            #print "debug(%d): %s" % (debug_type, debug_message)
            self.buf['debug'].append('ssl_data_in ({} bytes)'.format(len(debug_message)))

            io = StringIO.StringIO(debug_message)
            if io.len < 4:
                return

            type_length, = struct.unpack('!L', io.read(4))
            msg_type = type_length >> 24
            #msg_length = type_length & 0xffffff

            if msg_type == 11:
                length, = struct.unpack('!L', '\x00' + io.read(3))

                while length:
                    length2, = struct.unpack('!L', '\x00' + io.read(3))
                    certificate = io.read(length2)
                    #print repr(certificate)
                    #certs.append(certificate)
                    der = M2Crypto.X509.load_cert_der_string(certificate)
                    #print der.as_text()
                    self.buf['cert_chain'].append(der.as_text())
                    length -= 3 + length2

            io.close()

        elif debug_type == pycurl.INFOTYPE_SSL_DATA_OUT:
            self.buf['debug'].append('ssl_data_out ({} bytes)'.format(len(debug_message)))

        else:
            def istext(s):
                text_characters = "".join(map(chr, range(32, 127)) + list("\n\r\t\b"))
                _null_trans = string.maketrans("", "")
                if not s:
                    return True
                if "\0" in s:
                    return False
                # Get the non-text characters (maps a character to itself then
                # use the 'remove' option to get rid of the text characters.)
                t = s.translate(_null_trans, text_characters)
                # If more than 30% non-text characters, then consider it binary
                if len(t)/len(s) > 0.30:
                    return False
                return True
            if (istext(debug_message)):
                #print "debug({}): {}".format(debug_type, debug_message)
                self.buf['debug'].append(debug_message)
            else:
                #print "debug({}): {} non-text bytes".format(debug_type, len(debug_message))
                self.buf['debug'].append('data ({} bytes)'.format(len(debug_message)))

    def curl_header(self, buf):
        self.buf['header'] += buf

        match = re.match(r"^(?P<k>[^:]+):\s+(?P<v>[^\r]+)", buf)
        if match is not None:
            self.buf['headers'][match.group('k')] = match.group('v')
            
    def _edit_link(self, link):
        return "/s?psid={}&url={}".format(self.psid, urllib.quote(link))

    # Curl writes in ~16k chunks, 
    def curl_write(self, buf):
        #self.buf['debug'].append("writing ({} bytes)".format(len(buf)))
        self.buf['body'] += buf

        #doc = lxml.html.document_fromstring(buf)
        #doc.rewrite_links(self._edit_link, resolve_base_href=True, base_href=self.cfg['base_url'])
        #self.buf['body'] = lxml.html.tostring(doc)

    def to_json(self):
        #if len(self.buf['body']):
        #    doc = lxml.html.document_fromstring(self.buf['body'])
        #    doc.rewrite_links(self._edit_link, resolve_base_href=True, base_href=self.cfg['base_url'])
        #    self.buf['body'] = lxml.html.tostring(doc)
        #return json.dumps(self.buf)

        rv = []
        for buf in self._store['buffers']:
            if len(buf['body']):
                doc = lxml.html.document_fromstring(buf['body'])
                doc.rewrite_links(self._edit_link, resolve_base_href=True, base_href=self.cfg['base_url'])
                buf['body'] = lxml.html.tostring(doc)
            rv.append(buf)
        return json.dumps(rv)

class JSONResponse(object):
    """
    I'm just a wrapper for the responses that go back to the page
    """
    pass

class RootHandler(web.RequestHandler):
    def get(self):
        self.redirect('/static/main.html', permanent=False)

class WhirlRequestHandler(web.RequestHandler):
    ps = None

    def on_finish(self):
        if self.ps is not None:
            #self.ps.cfg.close()
            if hasattr(self.ps, 'buf'):
                self.ps.buf['body'] = ''
                self.ps._store.sync()
            self.ps._store.close()
            del self.ps
            self.ps = None

# Initial Request Handler
class InitialRequestHandler(WhirlRequestHandler):
    """
    The job of the IRH is to take the initial request from main.html to start
    loading a page. We take the requested URL and options, create a pseudo-
    session, do the initial request, and send back the reponse object, which
    should have both the HTML for the initial page load, and the meta
    information
    """
    def get(self):
        url = self.get_query_argument('url')
        e = calendar.timegm(time.gmtime())
        psid = md5.new(str(e)).hexdigest()
        self.ps = PseudoSession(psid, req=self)
        self.ps.buffer()
        self.ps.get(url)
        self.write(self.ps.to_json())
        self.ps.unbuffer()

# Subsequent Request Handler
class SubsequentRequestHandler(WhirlRequestHandler):
    def get(self):
        psid = self.get_query_argument('psid')
        url = self.get_query_argument('url')
        self.ps = PseudoSession(psid)
        self.ps.buffer()
        self.ps.get(url)

        self.write(self.ps.buf['body'])
        if 'Content-Type' in self.ps.buf['headers']:
            self.clear_header('Content-Type')
            self.add_header('Content-Type', self.ps.buf['headers']['Content-Type'])

# Update Request Handler
class UpdateRequestHandler(WhirlRequestHandler):
    pass

# Load Complete Handler
class LoadCompleteRequestHandler(WhirlRequestHandler):
    def get(self):
        psid = self.get_query_argument('psid')
        self.ps = PseudoSession(psid)
        self.write(self.ps.to_json())

_static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
application = web.Application([
    (r'/', RootHandler),
    (r'/i', InitialRequestHandler),
    (r'/s', SubsequentRequestHandler),
    (r'/u', UpdateRequestHandler),
    (r'/c', LoadCompleteRequestHandler),
    (r'/static/(.*)', web.StaticFileHandler, {'path': _static_path}),
    ], static_path=_static_path)

if __name__ == "__main__":
    application.listen(8888)
    tornado.options.parse_command_line()
    #tornado.ioloop.IOLoop.instance().start()

    io_loop = tornado.ioloop.IOLoop.instance()
    tornado.autoreload.start(io_loop)
    try:
        print "Starting Whirl main loop"
        io_loop.start()
    except KeyboardInterrupt:
        print "KeyboardInterrupt: pass"
        pass

