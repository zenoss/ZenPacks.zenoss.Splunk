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
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource \
    import PythonDataSource
from ZenPacks.zenoss.Splunk.datasources.SplunkSearchPerfDataSource \
    import SplunkSearchPerfInfo, ISplunkSearchPerfInfo


class SplunkSearchEventDataSource(PythonDataSource):

    """ Datasource used to capture datapoints for UGE from Splunk, or convert splunk search results into events """

    ZENPACKID = 'ZenPacks.zenoss.Splunk'

    sourcetypes = ('SplunkSearchEvent',)
    sourcetype = sourcetypes[0]
    security = ClassSecurityInfo()
    plugin_classname = 'ZenPacks.zenoss.Splunk.dsplugins.SplunkSearchEvent'

    splunkSearch = ''
    device_field = ''
    component_field = ''
    summary_field = ''

    def getDescription(self):
        return self.splunkSearch

    _properties = PythonDataSource._properties + (
        {'id': 'splunkSearch', 'type': 'string'},
        {'id': 'device_field', 'type': 'string'},
        {'id': 'component_field', 'type': 'string'},
        {'id': 'summary_field', 'type': 'string'},
    )


class ISplunkSearchEventInfo(ISplunkSearchPerfInfo):
    """ Info adapter """
    summary_field = schema.TextLine(title=_t(u'From Splunk query results, field from which to pull the event summary'))


class SplunkSearchEventInfo(SplunkSearchPerfInfo):
    """ Interface definition """
    implements(ISplunkSearchEventInfo)
    adapts(SplunkSearchEventDataSource)

    summary_field = ProxyProperty('summary_field')

