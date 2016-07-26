######################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is
# installed.
#
######################################################################

import Globals

from Products.ZenModel.ZenPack import ZenPack as ZenPackBase
from Products.ZenRelations.zPropertyCategory import setzPropertyCategory
from Products.ZenUtils.Utils import unused

unused(Globals)


setzPropertyCategory('zSplunkServer', 'Splunk')
setzPropertyCategory('zSplunkPort', 'Splunk')
setzPropertyCategory('zSplunkUsername', 'Splunk')
setzPropertyCategory('zSplunkPassword', 'Splunk')
setzPropertyCategory('zSplunkTimeout', 'Splunk')

class ZenPack(ZenPackBase):
    packZProperties = [
        ('zSplunkServer', '', 'string'),
        ('zSplunkPort', 8089, 'int'),
        ('zSplunkUsername', '', 'string'),
        ('zSplunkPassword', '', 'password'),
        ('zSplunkTimeout', '', 'string'),
    ]

