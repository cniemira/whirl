#
import os
import sys

import pycurl
import tornado.ioloop
import tornado.web as web

class RootHandler(web.RequestHandler):
    def get(self):
        self.redirect('/static/main.html', permanent=False)

class QHandler(web.RequestHandler):
    def get(self):
        q = self.get_query_argument('url')
        self.write(q)

        curl = pycurl.Curl()
        curl.setopt(c.URL, q)
        c.setopt(c.WRITEFUNCTION)

_static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
print _static_path
application = web.Application([
    (r'/', RootHandler),
    (r'/q', QHandler),
    (r'/static/(.*)', web.StaticFileHandler, {'path': _static_path}),
    ], static_path=_static_path)

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
