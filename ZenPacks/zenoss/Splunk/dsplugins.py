##############################################################################
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
import logging
import json

from twisted.internet import defer

from Products.ZenUtils.Utils import prepId
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.Splunk.libexec.check_splunk import ZenossSplunkPlugin as ZSP


class SplunkQuery(PythonDataSourcePlugin):
    """The base class for the ds plugin providing common methods.
    """
    log = logging.getLogger('zen.{}'.format(__name__))

    ######## upstream protocol methods ########
    @classmethod
    def config_key(cls, datasource, context):
        return (
                context.device().id,
                datasource.getCycleTime(context),
                datasource.id,
                datasource.plugin_classname
                )

    @classmethod
    def params(cls, datasource, context):
        """Method to setup required parameters.
        """
        return {
                'zSplunkServer': context.zSplunkServer,
                'zSplunkPort': context.zSplunkPort,
                'zSplunkUsername': context.zSplunkUsername,
                'zSplunkPassword': context.zSplunkPassword,
                'zSplunkTimeout': context.zSplunkTimeout,
                'splunkSearch': datasource.splunkSearch
                }

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        self.log.debug('DSPLUGINS: Success - sending CLEAR')
        for component in results['values'].keys():
            results['events'].insert(0, {
                'component': component,
                'summary': 'Collected successfully for component {}'.format(component),
                'eventClass': '/Status',
                'eventKey': 'splunk_collect_result',
                'severity': ZenEventClasses.Clear,
                })

        return results

    def onError(self, result, config):
        """Method to process results after an error during collection.
        """
        self.log.debug('DSPLUGINS: Collect failed: {}: {}'.format(config.id, result.getErrorMessage()))

        data = self.new_data()
        for component in config.datasources:
            data['events'].append({
                'component': component.component,
                'summary': 'Collect failed with: {}: {}'.format(config.id, result.getErrorMessage()),
                'eventClass': '/Status',
                'eventKey': 'splunk_collect_result',
                'severity': ZenEventClasses.Error,
                })
        return data

    @defer.inlineCallbacks
    def collect(self, config):
        """This must be overriden in your plugin
        """
        results = {}
        for datasource in config.datasources:
            if datasource.params['splunkSearch'].startswith('fake_splunk:'):
                filename = datasource.params['splunkSearch'].split(':',1)[1]
                with open(filename, 'r') as fh:
                    results[datasource.datasource] = json.load(fh)
            else:
                zsp = self.get_target(config)
                results[datasource.datasource] = yield zsp.run(datasource.params['splunkSearch'])
        defer.returnValue(results)

    def get_target(self, config):
        target = ZSP(
            config.datasources[0].params['zSplunkServer'] or config.datasources[0].device,
            config.datasources[0].params['zSplunkPort'],
            config.datasources[0].params['zSplunkUsername'],
            config.datasources[0].params['zSplunkPassword'],
            config.datasources[0].params['zSplunkTimeout']
            )
        return target


class MessageCount(SplunkQuery):
    """Collects counts of messages that match supplied search
    """

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        self.log.info('Processing splunk search results')
        to_return = self.new_data()


        for datasource in config.datasources:
            result = results.get(datasource.datasource, {})
            dps = zsp.count_results(result)
            # Process requested datapoints
            for datapoint_id in (x.id for x in datasource.points):
                if datapoint_id not in dps:
                    continue

                dpname = '_'.join((datasource.datasource, datapoint_id))

                value = dps[datapoint_id]

                to_return['values'][datasource.component][dpname] = (value, 'N')

        to_return = super(MessageCount, self).onSuccess(to_return, config)

        self.log.debug('TO_RETURN: {}'.format(to_return))
        
        return to_return

