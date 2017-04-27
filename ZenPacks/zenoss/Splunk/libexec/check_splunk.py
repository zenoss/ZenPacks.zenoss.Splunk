#!/usr/bin/env python
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2009, 2012, 2016-2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import os
import sys
import time
from cPickle import dump, load
from md5 import md5
from optparse import OptionParser
from tempfile import gettempdir

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue

import splunklib


def isNumeric(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


class ZenossSplunkPlugin:
    _state = None
    _server = None
    _port = None
    _username = None
    _password = None

    def __init__(self, server, port, username, password, timeout=10):
        self._server = server
        self._port = 8089
        if port:
            self._port = int(port)
        self._username = username
        self._password = password
        self._timeout = timeout
        self._loadState()

    def _loadState(self):
        state_filename = os.path.join(gettempdir(), 'check_splunk.pickle')
        if os.path.isfile(state_filename):
            try:
                state_file = open(state_filename, 'r')
                self._state = load(state_file)
                state_file.close()
            except Exception:
                print 'unable to load state from %s' % state_filename
                raise
        else:
            self._state = {
                'sessionkeys': {},
                }

    def _saveState(self):
        state_filename = os.path.join(gettempdir(), 'check_splunk.pickle')
        try:
            state_file = open(state_filename, 'w')
            dump(self._state, state_file)
            state_file.close()
        except Exception:
            print 'unable to save state in %s' % state_filename
            raise

    def cacheSessionKey(self, sessionkey):
        if not sessionkey:
            return

        key = md5('|'.join([self._server, str(self._port), self._username,
            self._password])).hexdigest()
        self._state['sessionkeys'][key] = sessionkey

    def getCachedSessionKey(self):
        key = md5('|'.join([self._server, str(self._port), self._username,
            self._password])).hexdigest()
        return self._state['sessionkeys'].get(key, None)

    def run(self, search, **kwargs):
        s = splunklib.Connection(
            self._server, self._port, self._username, self._password, self._timeout)

        # Try using a cached session key if we have one.
        s.setSessionKey(self.getCachedSessionKey())

        search = 'search %s' % search

        # Run our search job.
        sid = None
        try:
            sid = s.createSearch(search, **kwargs)
        except splunklib.Unauthorized:
            s.setSessionKey(None)
            sid = s.createSearch(search, **kwargs)

        # Periodically check back for the results of our query.
        results = None
        for i in [1, 2, 3, 5]:
            try:
                if s.getSearchStatus(sid) not in ("DONE", "FAILED"):
                    raise splunklib.NotFinished
                results = s.getSearchResults(sid)
                break
            except splunklib.NotFinished:
                time.sleep(i)
                continue

        # Cleanup after ourselves.
        self.cacheSessionKey(s.getSessionKey())
        self._saveState()
        try:
            s.deleteSearch(sid)
        except:
            pass
        return results

    @inlineCallbacks
    def run_nonblock(self, search, **kwargs):
        if search.startswith('fake_splunk:'):
            import json
            filename = search.split(':',1)[1]
            with open(filename, 'r') as fh:
                results = json.load(fh)
            returnValue(results)

        s = splunklib.Connection(
            self._server, self._port, self._username, self._password)

        # Try using a cached session key if we have one.
        s.setSessionKey(self.getCachedSessionKey())

        search = 'search %s' % search

        # Run our search job.
        sid = None
        try:
            sid = yield s.createSearch_nonblock(search, **kwargs)
        except splunklib.Unauthorized:
            s.setSessionKey(None)
            sid = yield s.createSearch_nonblock(search, **kwargs)

        # Periodically check back for the results of our query.
        results = None
        for i in [1, 2, 3, 5, 7, 10, 13, 15]:
            try:
                status = yield s.getSearchStatus_nonblock(sid)
                if status not in ("DONE", "FAILED"):
                    raise splunklib.NotFinished
                results = yield s.getSearchResults_nonblock(sid)
                break
            except splunklib.NotFinished:
                time.sleep(i)
                continue

        # Cleanup after ourselves.
        self.cacheSessionKey(s.getSessionKey())
        self._saveState()
        try:
            yield s.deleteSearch_nonblock(sid)
        except:
            pass
        returnValue(results)


    def count_results(self, output):
        if not output:
            print "no results from Splunk search"
            return

        results = output.get('results', [])
        fielddicts = output.get('fields', {})
        fields = [x['name'] for x in fielddicts]
        count = len(results)

        dps = {}

        if count == 1:
            for result in results:
                # Key/Value Result:
                #
                # count         1447

                if len(fields) == 1:
                    for field in fields:
                        value = result.get(field, [None])
                        if not isNumeric(value):
                            continue

                        dps[field] = value

                # Tabular Result:
                #
                # sourcetype    count    percent
                # syslog        1447     100.000000

                elif len(fields) > 1:
                    prefix = result.get(fields[0])
                    for field in fields[1:]:
                        value = result.get(field, [None])
                        if not isNumeric(value):
                            continue

                        key = '_'.join(( prefix, field))
                        dps[key] = value

        dps.setdefault('count', count)
        return dps

    def print_nagios(self, dps):
        print "OK|%s" % ' '.join(['%s=%s' % (x, y) for x, y in dps.items()])

@inlineCallbacks
def main(zsp, args):
    results = yield zsp.run_nonblock(' '.join(args))
    import json
    print json.dumps(results)
    if reactor.running:
        reactor.stop()

def errback(failure):
   print failure
   reactor.stop()

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-s', '--server', dest='server',
        help='Hostname or IP address of Splunk server')
    parser.add_option('-p', '--port', dest='port',
        help='splunkd port on Splunk server')
    parser.add_option('-u', '--username', dest='username',
        help='Splunk username')
    parser.add_option('-w', '--password', dest='password',
        help='Splunk password')
    parser.add_option('-n', '--nonblock', dest='nonblock',
        default=False, action="store_true", help='Splunk password')
    options, args = parser.parse_args()

    if not options.server:
        if 'SPLUNK_SERVER' in os.environ:
            options.server = os.environ['SPLUNK_SERVER']
        else:
            print 'no Splunk server specified'
            sys.exit(1)

    if not options.port:
        if 'SPLUNK_PORT' in os.environ:
            options.port = os.environ['SPLUNK_PORT']
        else:
            options.port = 8089

    if not options.username:
        options.username = os.environ.get('SPLUNK_USERNAME', '')

    if not options.password:
        options.password = os.environ.get('SPLUNK_PASSWORD', '')

    if len(args) < 1:
        print 'no Splunk search specified'
        sys.exit(1)

    zsp = ZenossSplunkPlugin(
        options.server, options.port, options.username, options.password)

    if options.nonblock:
        d = main(zsp, args)
        d.addErrback(errback)
        if not d.called:
            reactor.run()
    else:
        try:
            results = zsp.run(' '.join(args))
            if not results:
                print "no results from Splunk search"
                sys.exit(0)

        except splunklib.Unauthorized, ex:
            print "invalid Splunk username or password"
            sys.exit(1)
        except splunklib.Failure, ex:
            print ex
            sys.exit(1)
        dps = splunklib.count_results(results)
        zsp.print_nagios(dps)

