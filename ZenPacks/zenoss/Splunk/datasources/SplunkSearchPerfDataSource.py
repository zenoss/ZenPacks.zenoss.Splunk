###########################################################################
#
# Copyright (C) 2016, Zenoss Inc.
#
#
###########################################################################

from zope.component import adapts
from zope.interface import implements

from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from AccessControl import ClassSecurityInfo
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSource
from ZenPacks.zenoss.Splunk.datasources.SplunkSearchDataSource \
    import SplunkSearchInfo, ISplunkSearchInfo


class SplunkSearchPerfDataSource(PythonDataSource):

    """ Datasource used to capture datapoints from Splunk query results """

    ZENPACKID = 'ZenPacks.zenoss.Splunk'

    sourcetypes = ('SplunkSearchPerf',)
    sourcetype = sourcetypes[0]
    security = ClassSecurityInfo()
    plugin_classname = 'ZenPacks.zenoss.Splunk.dsplugins.SplunkSearchPerf'

    splunkSearch = ''
    device_field = ''
    component_field = ''

    def getDescription(self):
        return self.splunkSearch

    _properties = PythonDataSource._properties + (
        {'id': 'splunkSearch', 'type': 'string'},
        {'id': 'device_field', 'type': 'string'},
        {'id': 'component_field', 'type': 'string'},
    )


class ISplunkSearchPerfInfo(ISplunkSearchInfo):
    """ Info adapter """
    device_field = schema.TextLine(title=_t(u'Field to match against Device ID'))
    component_field = schema.TextLine(title=_t(u'Field to match against Component ID'))


class SplunkSearchPerfInfo(SplunkSearchInfo):
    """ Interface definition """
    implements(ISplunkSearchPerfInfo)
    adapts(SplunkSearchPerfDataSource)

    device_field = ProxyProperty('device_field')
    component_field = ProxyProperty('component_field')

