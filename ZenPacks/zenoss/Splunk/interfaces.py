###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2010, 2016-2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from Products.Zuul.interfaces import IRRDDataSourceInfo
from Products.Zuul.form import schema
from Products.Zuul.utils import ZuulMessageFactory as _t


class ISplunkDataSourceInfo(IRRDDataSourceInfo):
    timeout = schema.Int(title=_t(u"Timeout (seconds)"))
    component = schema.TextLine(title=_t(u"Component"))
    eventKey = schema.TextLine(title=_t(u"Event Key"))

    splunkServer = schema.TextLine(
        title=_t(u"Splunk Server"),
        group=_t('Splunk'))

    splunkUsername = schema.TextLine(
        title=_t(u"Splunk Username"),
        group=_t('Splunk'))

    splunkPort = schema.Int(
        title=_t(u"Splunk Port"),
        group=_t('Splunk'))

    splunkPassword = schema.Password(
        title=_t(u"Splunk Password"),
        group=_t('Splunk'))

    splunkCount = schema.TextLine(
        title=_t(u"Maximum Result Count"),
        group=_t('Splunk'))

    splunkSearch = schema.Text(
        title=_t(u"Search"),
        group=_t('Splunk'),
        xtype='twocolumntextarea')
