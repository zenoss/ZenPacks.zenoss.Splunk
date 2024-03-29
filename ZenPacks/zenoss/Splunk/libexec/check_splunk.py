#!/usr/bin/env python
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2009, 2012, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import os
import random
import sys
import time
from cPickle import dump, load
from md5 import md5
from optparse import OptionParser
from tempfile import gettempdir
from xml.dom.minidom import parseString

import splunklib


def getText(element):
    return element.childNodes[0].data


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

    def __init__(self, server, port, username, password):
        self._server = server
        self._port = int(port)
        self._username = username
        self._password = password

    def _loadState(self):
        state_filename = os.path.join(gettempdir(), 'check_splunk.pickle')
        if os.path.isfile(state_filename):
            try:
                state_file = open(state_filename, 'r')
                self._state = load(state_file)
                state_file.close()
            except Exception:
                print 'unable to load state from %s' % state_filename
                sys.exit(1)
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
            sys.exit(1)

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

    def run(self, search, timeout=60, **kwargs):
        start_time = time.time()

        self._loadState()
        s = splunklib.Connection(
            self._server, self._port, self._username, self._password)

        # Try using a cached session key if we have one.
        s.setSessionKey(self.getCachedSessionKey())

        search = 'search %s' % search

        # Run our search job.
        sid = None
        try:
            sid = s.createSearch(search, **kwargs)
        except splunklib.Unauthorized:
            s.setSessionKey(None)

            try:
                sid = s.createSearch(search, **kwargs)
            except splunklib.Unauthorized, ex:
                print "invalid Splunk username or password"
                sys.exit(1)
        except splunklib.Failure, ex:
            print ex
            sys.exit(1)

        results = None
        timed_out = False

        # Periodically check back for the results of our query.
        for retry in xrange(sys.maxint):
            try:
                results = s.getSearchResults(sid, **kwargs)
                break
            except splunklib.NotFinished:
                time_left = timeout - (time.time() - start_time)

                if time_left <= 1:
                    timed_out = True
                    break

                # incremental backoff.
                delay = (random.random() * pow(4, retry)) / 10.0
                delay = min(delay, time_left - 1)
                time.sleep(delay)
            except Exception:
                break

        # Cleanup after ourselves.
        self.cacheSessionKey(s.getSessionKey())
        self._saveState()
        try:
            s.deleteSearch(sid)
        except:
            pass

        if timed_out:
            print "Splunk search timed out after %s seconds" % timeout
            sys.exit(1)

        if not results:
            print "no results from Splunk search"
            sys.exit(1)

        xml = parseString(results)
        results = xml.getElementsByTagName('result')
        count = len(results)

        dps = {}

        if count > 0:
            for result in results:
                fields = result.getElementsByTagName('field')

                # Key/Value Result:
                #
                # count         1447

                if len(fields) == 1:
                    for field in result.getElementsByTagName('field'):
                        key = field.getAttribute('k').lstrip('_')

                        values = field.getElementsByTagName('text')
                        if len(values) < 1:
                            continue

                        value = getText(values[0])
                        if not isNumeric(value):
                            continue

                        dps[key] = value

                # Tabular Result:
                #
                # sourcetype    count    percent
                # syslog        1447     100.000000

                elif len(fields) > 1:
                    prefix = getText(fields[0].getElementsByTagName('text')[0])
                    if prefix.startswith('main~'):
                        continue

                    for field in fields[1:]:
                        value = field.getElementsByTagName('text')
                        value = len(value) and getText(value[0]) or None
                        if not isNumeric(value):
                            continue

                        key = '_'.join((
                            prefix, field.getAttribute('k').lstrip('_')))

                        dps[key] = value

        dps.setdefault('count', count)

        print "OK|%s" % ' '.join(['%s=%s' % (x, y) for x, y in dps.items()])
        sys.exit(0)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option(
        '-s', '--server', dest='server',
        help='Hostname or IP address of Splunk server')

    parser.add_option(
        '-p', '--port', dest='port',
        help='splunkd port on Splunk server')

    parser.add_option(
        '-u', '--username', dest='username',
        help='Splunk username')

    parser.add_option(
        '-w', '--password', dest='password',
        help='Splunk password')

    parser.add_option(
        '-c', '--count', dest='count',
        default="100",
        help='Maximum number of results [default: %default]')

    parser.add_option(
        '-t', '--timeout', dest='timeout',
        type='int', default=60,
        help='Query timeout in seconds [default: %default]')

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

    zsp.run(' '.join(args), timeout=options.timeout, count=options.count)
