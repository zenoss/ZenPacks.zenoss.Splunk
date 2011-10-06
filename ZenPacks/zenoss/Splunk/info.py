###########################################################################
#
# Copyright 2010 Zenoss, Inc.  All Rights Reserved.
#
###########################################################################
from Products.Zuul.infos import ProxyProperty
from zope.interface import implements
from Products.Zuul.infos.template import BasicDataSourceInfo
from ZenPacks.zenoss.Splunk.interfaces import ISplunkDataSourceInfo


class SplunkDataSourceInfo(BasicDataSourceInfo):
    implements(ISplunkDataSourceInfo)
    component = ProxyProperty('component')
    eventKey = ProxyProperty('eventKey')
    timeout = ProxyProperty('timeout')
    splunkServer = ProxyProperty('splunkServer')
    splunkPort = ProxyProperty('splunkPort')
    splunkUsername = ProxyProperty('splunkUsername')
    splunkPassword = ProxyProperty('splunkPassword')
    splunkSearch = ProxyProperty('splunkSearch')
    
    @property
    def testable(self):
        """
        We can NOT test this datsource against a specific device
        """
        return False
    


