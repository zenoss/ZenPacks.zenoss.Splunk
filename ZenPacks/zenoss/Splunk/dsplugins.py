##############################################################################
# Copyright (C) Zenoss, Inc. 2016-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
import logging
import json

from twisted.internet import defer

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.Splunk.libexec.check_splunk import ZenossSplunkPlugin as ZSP


class SplunkQuery(PythonDataSourcePlugin):
    """The base class for the iSplunk ds plugins providing common methods.
    """
    log = logging.getLogger('zen.{}'.format(__name__))

    event_class_key = 'SplunkQuery'

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
                'splunkSearch': datasource.talesEval(datasource.splunkSearch, context)
                }

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        logname = self.__class__.__name__
        self.log.debug('%s: Success - sending CLEAR', logname)
        seen = []
        for datasource in config.datasources:
            search = datasource.params.get('splunkSearch')
            if search in seen:
                continue
            seen.append(search)
            results['events'].insert(0, {
                'summary': 'Collection successful for {}'.format(datasource.datasource),
                'eventClass': datasource.eventClass,
                'eventClassKey': self.event_class_key,
                'eventKey': search,
                'severity': ZenEventClasses.Clear,
                })

        return results

    def onError(self, result, config):
        """Method to process results after an error during collection.
        """
        logname = self.__class__.__name__
        self.log.debug('{}: Collect failed - {}: {}'.format(logname, config.id, result.getErrorMessage()))

        data = self.new_data()
        seen = []
        for datasource in config.datasources:
            search = datasource.params.get('splunkSearch')
            if search in seen:
                continue
            seen.append(search)
            data['events'].append({
                'summary': 'Collect failed for {} with: {}'.format(datasource.datasource, result.getErrorMessage()),
                'eventClass': datasource.eventClass,
                'eventClassKey': self.event_class_key,
                'eventKey': search,
                'severity': ZenEventClasses.Error,
                })
        return data

    @defer.inlineCallbacks
    def collect(self, config):
        """ This must be overriden in your plugin, as it merely performs the query and returns the raw results
        """
        logname = self.__class__.__name__
        results = {}
        for datasource in config.datasources:
            if datasource.params['splunkSearch'] in results:
                continue
            self.log.debug("%s search: %r", (logname, datasource.params.get('splunkSearch')))
            if datasource.params['splunkSearch'].startswith('fake_splunk:'):
                filename = datasource.params['splunkSearch'].split(':',1)[1]
                with open(filename, 'r') as fh:
                    results[datasource.params['splunkSearch']] = json.load(fh)
            else:
                zsp = self.get_target(config)
                results[datasource.params['splunkSearch']] = yield zsp.run_nonblock(datasource.params['splunkSearch'])
        defer.returnValue(results)

    def get_target(self, config):
        dsource = config.datasources[0]
        target = ZSP(
            dsource.params['zSplunkServer'] or dsource.device,
            dsource.params['zSplunkPort'],
            dsource.params['zSplunkUsername'],
            dsource.params['zSplunkPassword'],
            dsource.params['zSplunkTimeout']
            )
        return target


class MessageCount(SplunkQuery):
    """Collects counts of messages that match supplied search or for single row tabular data,
    returns values for datapoints that match the field names
    """

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        logname = self.__class__.__name__
        self.log.debug('Processing Splunk %s results', logname)
        to_return = self.new_data()

        zsp = self.get_target(config)
        for datasource in config.datasources:
            result = results.get(datasource.params['splunkSearch'], {})
            dps = zsp.count_results(result)
            # Process requested datapoints
            for datapoint_id in (x.id for x in datasource.points):
                if datapoint_id not in dps:
                    continue

                dpname = '_'.join((datasource.datasource, datapoint_id))
                value = dps[datapoint_id]
                to_return['values'][datasource.component][dpname] = (value, 'N')

        to_return = super(MessageCount, self).onSuccess(to_return, config)
        self.log.debug('Splunk {} TO_RETURN: {}'.format(logname, to_return))
        return to_return


class SplunkSearchPerf(SplunkQuery):
    """Collects numerical values from splunk queries

       The query should return a result with one row per device/component.
       Each fieldname that matches a datapoint name and contains a numerical value will be stored
       for that datapoint on that device/component.
       if device_field and/or component_field are non-empty strings, only matching records will be processed.

       eg.
       Query:
          index=${dev/id} sourcetype=accounting owner!=root | stats dc(job_number) by index | rename dc(job_number) as "Jobs Submitted" |
            appendcols [search index=${dev/id} sourcetype=accounting failed=0 submission_time!=0 owner!=root |
                          stats dc(job_number) by index | rename dc(job_number) as "Successful Jobs"]
       Result:
          {"fields": [{"name": "index", "groupby_rank": "0"}, {"name": "JobsSubmitted"}, {"name": "SuccessfulJobs"}],
           "messages": [{"text": "Your timerange was substituted based on your search string", "type":"INFO"},
                        {"text": "[subsearch]: Your timerange was substituted based on your search string", "type": "INFO"}],
           "results": [{"index": "mydevice", "JobsSubmitted": "87", "SuccessfulJobs": "85"}],
           "highlighted": {},
           "preview": false,
           "init_offset": 0}

    """

    event_class_key = 'SplunkSearchPerf'

    @classmethod
    def params(cls, datasource, context):
        myparams = super(SplunkSearchPerf, cls).params(datasource, context)
        myparams.update({
                         'device_field': datasource.device_field,
                         'component_field': datasource.component_field
                        })
        return myparams

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        logname = self.__class__.__name__
        self.log.debug('%s: Processing splunk search results', logname)
        to_return = self.new_data()

        for datasource in config.datasources:
            device_field = datasource.params['device_field']
            component_field = datasource.params['component_field']
            result = results.get(datasource.params['splunkSearch'], {})
            for dps in result.get('results', []):
                # result will have a list of dicts with device_field containing the device id to match
                # and the remaining items being the search result column/value pairs
                if (not datasource.device or dps.get(device_field, None) == datasource.device) and (not datasource.component or dps.get(component_field, None) == datasource.component):
                    # Process requested datapoints
                    for datapoint_id in (x.id for x in datasource.points):
                        if datapoint_id not in dps:
                            continue

                        dpname = '_'.join((datasource.datasource, datapoint_id))

                        value = dps[datapoint_id]

                        to_return['values'][datasource.component][dpname] = (value, 'N')

        to_return = super(SplunkSearchPerf, self).onSuccess(to_return, config)

        self.log.debug('{}: TO_RETURN: {}'.format(logname, to_return))

        return to_return


class SplunkSearchEvent(SplunkSearchPerf):
    """Generates events from any messages returned from a splunk query
       If device_field and/or component_field are non-empty strings, only matching records will be processed.
       If summary_field is a non-empty string, the matching field content will be used for the event summary,
       otherwise the '_raw' field will be used for the event summary.
       If the summary_field field is not present, the event summary will contian a message indicating this.
       The event message will contain the contents of the '_raw' field.
    """

    event_class_key = 'SplunkSearchEvent'

    @classmethod
    def params(cls, datasource, context):
        myparams = super(SplunkSearchEvent, cls).params(datasource, context)
        myparams.update({
                         'summary_field': datasource.summary_field,
                        })
        return myparams

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        logname = self.__class__.__name__
        self.log.debug('%s: Processing splunk search results', logname)
        to_return = self.new_data()

        for datasource in config.datasources:
            summary_field = datasource.params['summary_field']
            device_field = datasource.params['device_field']
            component_field = datasource.params['component_field']

            result = results.get(datasource.params['splunkSearch'], {})
            for dps in result.get('results', []):
                # result will have a list of dicts with device_field containing the device id to match
                # and the remaining items being the search result column/value pairs
                if (not datasource.device or dps.get(device_field, None) == datasource.device) and (not datasource.component or dps.get(component_field, None) == datasource.component):
                    # Process requested datapoints
                    to_return['events'].insert(0, {
                        'component': datasource.component,
                        'summary': dps.get(summary_field or '_raw', 'Field {} not found in returned record'.format(summary_field) ),
                        'message': "%r" % dps,
                        'eventClass': datasource.eventClass,
                        'eventKey': self.event_class_key,
                        'severity': datasource.severity,
                        })

        self.log.debug('{}: TO_RETURN: {}'.format(logname, to_return))

        return to_return

