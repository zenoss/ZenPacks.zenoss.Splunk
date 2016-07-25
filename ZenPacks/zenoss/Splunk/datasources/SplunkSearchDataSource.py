###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2009, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from Products.ZenModel.BasicDataSource import BasicDataSource
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource \
    import PythonDataSource, PythonDataSourceInfo, IPythonDataSourceInfo
from Products.ZenModel.ZenPackPersistence import ZenPackPersistence
from Products.ZenModel.ZenossSecurity import ZEN_VIEW
from Products.ZenWidgets import messaging

from zope.component import adapts
from zope.interface import implements

from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from AccessControl import ClassSecurityInfo
from Products.ZenModel.ZenossSecurity import ZEN_MANAGE_DMD


class SplunkSearchDataSource(PythonDataSource):

    """Datasource used to capture datapoints from TSM select statements"""

    ZENPACKID = 'ZenPacks.zenoss.Splunk'

    sourcetypes = ('SplunkSearch',)
    sourcetype = sourcetypes[0]
    security = ClassSecurityInfo()
    plugin_classname = 'ZenPacks.zenoss.Splunk.dsplugins.MessageCount'

    splunkSearch = ''

    def getDescription(self):
        return self.splunkSearch

    _properties = PythonDataSource._properties + (
        {'id': 'splunkSearch', 'type': 'string'},
    )


class ISplunkSearchInfo(IPythonDataSourceInfo):
    """ Info adapter """
    splunkSearch = schema.TextLine(title=_t(u'Search query'))


class SplunkSearchInfo(PythonDataSourceInfo):
    """ Interface definition """
    implements(ISplunkSearchInfo)
    adapts(SplunkSearchDataSource)

    splunkSearch = ProxyProperty('splunkSearch')

