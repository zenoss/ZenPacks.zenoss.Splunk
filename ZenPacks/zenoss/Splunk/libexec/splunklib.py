###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2009, 2012, 2016 Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from httplib import HTTPSConnection
from urllib import urlencode
from xml.dom.minidom import parseString
import json

from twisted.web.client import getPage
from twisted.internet.defer import inlineCallbacks, returnValue


class Unauthorized(Exception):
    pass


class Failure(Exception):
    pass


class NotFinished(Exception):
    pass

def count_results(output):
    """
    Generic processor of Splunk search results
    Returns a dictionary of field values and a count of matching records
    The number of matching records (or more correctly number of rows returned
    in the key 'count'
    If tabular results are returned, the keys will be field_column and the value
    will be the value of that column for that field.
    """

    if not output:
        return {}

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
                    try:
                        float(value)
                    except ValueError:
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
                    try:
                        float(value)
                    except ValueError:
                        continue

                    key = '_'.join(( prefix, field))
                    dps[key] = value

    dps.setdefault('count', count)
    return dps


class Connection:
    _server = None
    _port = None
    _credentials = None
    _sessionkey = None
    timeout = 10

    def __init__(self, server, port, username, password, timeout=10):
        self._server = server
        self._port = port
        self.timeout = timeout

        # The free versions of Splunk requires no authentication.
        if username and password:
            self._credentials = urlencode(
                {'username': username, 'password': password})

    def setSessionKey(self, sessionkey):
        self._sessionkey = sessionkey

    def getSessionKey(self):
        if not self._credentials:
            return

        if self._sessionkey:
            return self._sessionkey

        h = HTTPSConnection(self._server, self._port)
        h.request('POST', '/services/auth/login/', self._credentials)
        r = h.getresponse()
        content = r.read()

        if r.status != 200:
            raise Unauthorized('Server responded with code %s' % r.status)

        if len(content) < 1:
            raise Unauthorized('No response to authentication attempt')
        xml = parseString(content)
        elements = xml.getElementsByTagName('sessionKey')
        if len(elements) < 1:
            raise Unauthorized('No session key returned from authentication')

        self._sessionkey = elements[0].firstChild.nodeValue
        return self._sessionkey

    def getHeaders(self):
        headers = {'Content-type': 'application/x-www-form-urlencoded'}

        session_key = self.getSessionKey()
        if session_key:
            headers['Authorization'] = 'Splunk %s' % session_key

        return headers

    def _request(self, method, url, body=None):
        h = HTTPSConnection(self._server, self._port)
        h.request(method, url, body, self.getHeaders())
        r = h.getresponse()
        return r, r.read()

    def createSearch(self, search, **kwargs):
        kwargs.update({'search': search})
        kwargs.update({'output_mode': 'json'})
        body = urlencode(kwargs)
        r, content = self._request('POST', '/services/search/jobs/', body)

        if r.status == 401:
            raise Unauthorized('Server responded with code %s' % r.status)
        elif r.status != 201:
            raise Failure('Server responded with code %s' % r.status)

        if len(content) < 1:
            raise Failure('No response to job creation attempt')

        result = json.loads(content)
        sid = result.get('sid')
        if not sid:
            raise Failure('No sid returned from job creation')

        return sid


    def getSearchStatus(self, sid, **kwargs):
        kwargs.update({'output_mode': 'json'})
        params = urlencode(kwargs)
        if params:
            params = '?%s' % params

        r, content = self._request(
            'GET', '/services/search/jobs/%s%s' % (sid, params))

        if r.status == 204:
            raise NotFinished('Job still processing. Try again later')
        elif r.status != 200:
            raise Failure('Server returned code %s' % r.status)

        if len(content) < 1:
            raise Failure('No response for job results')

        results = json.loads(content)
        entries = results.get('entry', [])
        if len(entries) < 1:
            raise Failure('No content returned from job status')

        entry = entries[0]
        return entry.get('content', {}).get('dispatchState', 'Unknown')

    def getSearchResults(self, sid, **kwargs):
        kwargs.update({'output_mode': 'json'})
        params = urlencode(kwargs)
        if params:
            params = '?%s' % params

        r, content = self._request(
            'GET', '/services/search/jobs/%s/results%s' % (sid, params))

        if r.status == 204:
            raise NotFinished('Job still processing. Try again later')
        elif r.status != 200:
            raise Failure('Server returned code %s' % r.status)

        if len(content) < 1:
            raise Failure('No response for job results')

        return json.loads(content)

    def deleteSearch(self, sid):
        r, content = self._request('DELETE', '/services/search/jobs/%s' % sid)

    #
    # non-blocking path for the above
    #

    def mkurl(self, url):
        return '{}://{}:{}{}'.format('HTTPS', self._server, self._port, url)

    @inlineCallbacks
    def getSessionKey_nonblock(self):
        if not self._credentials:
            returnValue(None)

        if self._sessionkey:
            returnValue(self._sessionkey)

        headers = {'Content-type': 'application/x-www-form-urlencoded'}
        try:
            content = yield getPage(self.mkurl('/services/auth/login/'),
                                    method='POST',
                                    postdata=self._credentials,
                                    headers=headers,
                                    cookies={},
                                    timeout=self.timeout)
        except Exception:
            #raise Unauthorized('Exception hit during auth attempt')
            raise

        if content:
            xml = parseString(content)
            elements = xml.getElementsByTagName('sessionKey')
            if len(elements) < 1:
                raise Unauthorized('No session key returned from authentication')

            self._sessionkey = elements[0].firstChild.nodeValue
            returnValue(self._sessionkey)

    @inlineCallbacks
    def getHeaders_nonblock(self):
        headers = {'Content-type': 'application/x-www-form-urlencoded'}

        session_key = yield self.getSessionKey_nonblock()
        if session_key:
            headers['Authorization'] = 'Splunk %s' % session_key

        returnValue(headers)

    @inlineCallbacks
    def _request_nonblock(self, method, url, body=None):
        headers = yield self.getHeaders_nonblock()
        if method == 'POST':
            result = yield getPage(self.mkurl(url),
                                   method=method,
                                   headers=headers,
                                   postdata=body,
                                   cookies={},
                                   timeout=self.timeout)
        else:
            result = yield getPage(self.mkurl(url),
                                   method=method,
                                   headers=headers,
                                   cookies={},
                                   timeout=self.timeout)
        returnValue(result)

    @inlineCallbacks
    def createSearch_nonblock(self, search, **kwargs):
        kwargs.update({'search': search})
        kwargs.update({'output_mode': 'json'})
        body = urlencode(kwargs)
        content = yield self._request_nonblock('POST', '/services/search/jobs/', body)

        result = json.loads(content)
        if not result:
            raise Failure('No result returned from job creation')
        sid = result.get('sid')
        if not sid:
            raise Failure('No sid returned from job creation')

        returnValue(sid)

    @inlineCallbacks
    def getSearchStatus_nonblock(self, sid, **kwargs):
        kwargs.update({'output_mode': 'json'})
        params = urlencode(kwargs)
        if params:
            params = '?%s' % params

        content = yield self._request_nonblock(
            'GET', '/services/search/jobs/%s%s' % (sid, params))

        results = json.loads(content)
        entries = results.get('entry', [])
        if len(entries) < 1:
            raise Failure('No content returned from job status')

        entry = entries[0]
        returnValue(entry.get('content', {}).get('dispatchState', 'Unknown'))

    @inlineCallbacks
    def getSearchResults_nonblock(self, sid, **kwargs):
        kwargs.update({'output_mode': 'json', 'count': 0})
        params = urlencode(kwargs)
        if params:
            params = '?%s' % params

        content = yield self._request_nonblock(
            'GET', '/services/search/jobs/%s/results%s' % (sid, params))

        returnValue(json.loads(content))

    @inlineCallbacks
    def deleteSearch_nonblock(self, sid):
        content = yield self._request_nonblock('DELETE', '/services/search/jobs/%s' % sid)
        returnValue(content)

