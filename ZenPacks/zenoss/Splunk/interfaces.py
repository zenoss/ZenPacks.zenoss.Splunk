###########################################################################
#
# Copyright 2010 Zenoss, Inc.  All Rights Reserved.
#
###########################################################################
from Products.Zuul.interfaces import IBasicDataSourceInfo
from Products.Zuul.form import schema
from Products.Zuul.utils import ZuulMessageFactory as _t


class ISplunkDataSourceInfo(IBasicDataSourceInfo):
    timeout = schema.Int(title=_t(u"Timeout (seconds)"))
    component = schema.TextLine(title=_t(u"Component"))
    eventKey = schema.TextLine(title=_t(u"Event Key"))
    
    splunkServer = schema.TextLine(title=_t(u"Splunk Server"),
                                   group=_t('Splunk'))
    splunkUsername = schema.TextLine(title=_t(u"Splunk Username"),
                                     group=_t('Splunk'))
    splunkPort = schema.Int(title=_t(u"Splunk Port"),
                            group=_t('Splunk'))
    splunkPassword = schema.Password(title=_t(u"Splunk Password"),
                                     group=_t('Splunk'))
    splunkSearch = schema.TextLine(title=_t(u"Search"),
                                   group=_t('Splunk'))
