'''
Created on Aug 29, 2009

@author: Nick
'''
import logging, os, sys

# Google App Engine imports.
from google.appengine.ext.webapp import util
from google.appengine.dist import use_library
use_library('django', '1.0')

# Remove the standard version of Django.
#for k in [k for k in sys.modules if k.startswith('django')]:
#    del sys.modules[k]

# Force sys.path to have our own directory first, in case we want to import
# from it.
#sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Must set this env var *before* importing any part of Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django.core.handlers.wsgi
import django.core.signals
import django.db
import django.dispatch.dispatcher

def log_exception(*args, **kwds):
    logging.exception('Exception in request:')

# Log errors.
# Django 0.96
#django.dispatch.dispatcher.connect(
#   log_exception, django.core.signals.got_request_exception)
# Django 1.0+
django.core.signals.got_request_exception.connect(log_exception)

# Unregister the rollback event handler.
# Django 0.96
#django.dispatch.dispatcher.disconnect(
#        django.db._rollback_on_exception,
#        django.core.signals.got_request_exception)
# Django 1.0+
django.core.signals.got_request_exception.disconnect(
        django.db._rollback_on_exception)

def main():
#    form = cgi.FieldStorage()
#    if form.has_key('content'):
#        sys.stderr.write("Content: " + form['content'].value)
    # Create a Django application for WSGI.
    application = django.core.handlers.wsgi.WSGIHandler()

    # Run the WSGI CGI handler with that application.
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
