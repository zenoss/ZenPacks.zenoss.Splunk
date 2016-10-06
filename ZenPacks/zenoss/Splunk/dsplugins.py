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
        self.log.debug('SplunkSearch: Success - sending CLEAR')
        for datasource in config.datasources:
            results['events'].insert(0, {
                'component': datasource.component,
                'summary': 'Collection successful for {}'.format(datasource.datasource),
                'eventClass': datasource.eventClass,
                'eventClassKey': self.event_class_key,
                'severity': ZenEventClasses.Clear,
                })

        return results

    def onError(self, result, config):
        """Method to process results after an error during collection.
        """
        self.log.debug('SplunkSearch: Collect failed: {}: {}'.format(config.id, result.getErrorMessage()))

        data = self.new_data()
        for datasource in config.datasources:
            data['events'].append({
                'component': datasource.component,
                'summary': 'Collect failed for {} with: {}'.format(datasource.datasource, result.getErrorMessage()),
                'eventClass': datasource.eventClass,
                'eventClassKey': self.event_class_key,
                'severity': ZenEventClasses.Error,
                })
        return data

    @defer.inlineCallbacks
    def collect(self, config):
        """This must be overriden in your plugin
        """
        results = {}
        for datasource in config.datasources:
            if datasource.params['splunkSearch'] in results:
                continue
            self.log.debug("Splunk search: %r", datasource.params.get('splunkSearch'))
            if datasource.params['splunkSearch'].startswith('fake_splunk:'):
                filename = datasource.params['splunkSearch'].split(':',1)[1]
                with open(filename, 'r') as fh:
                    results[datasource.params['splunkSearch']] = json.load(fh)
            else:
                zsp = self.get_target(config)
                results[datasource.params['splunkSearch']] = yield zsp.run_nonblock(datasource.params['splunkSearch'])
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
        self.log.debug('Processing splunk search results')
        to_return = self.new_data()


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

        self.log.debug('Splunk MessageCount TO_RETURN: {}'.format(to_return))
        
        return to_return


class SplunkSearchPerf(SplunkQuery):
    """Collects numerical values from splunk queries

       The query should return a result with one row per device/component.
       Each fieldname that matches a datapoint name and contains a numerical value will be stored
       for that datapoint on that device/component.
       if device_field and/or component_field are non-empty strings, only matching records will be processed.

       eg.
       Query: 
          index=${dev/id} sourcetype=uge_accounting owner!=root | stats dc(job_number) by index | rename dc(job_number) as "Jobs Submitted" |
            appendcols [search index=${dev/id} sourcetype=uge_accounting failed=0 submission_time!=0 owner!=root |
                          stats dc(job_number) by index | rename dc(job_number) as "Successful Jobs"]
       Result:
          {"fields": [{"name": "index", "groupby_rank": "0"}, {"name": "JobsSubmitted"}, {"name": "SuccessfulJobs"}],
           "messages": [{"text": "Your timerange was substituted based on your search string", "type":"INFO"},
                        {"text": "[subsearch]: Your timerange was substituted based on your search string", "type": "INFO"}],
           "results": [{"index": "seis", "JobsSubmitted": "87", "SuccessfulJobs": "85"}],
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
        self.log.debug('SplunkSearchPerf: Processing splunk search results')
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

        self.log.debug('SplunkSearchPerf: TO_RETURN: {}'.format(to_return))

        return to_return


class SplunkSearchEvent(SplunkSearchPerf):
    """Generates evens from any messages returned from a splunk query
       If device_field and/or component_field are non-empty strings, only matching records will be processed.
       If summary_field is a non-empty string, the matching field content will be used for the event summary,
       otherwise the _raw field will be used for the event summary.
       If the summary_field field is not present, the event summary will contian a message indicating this.
       The event message will contain the contents of the _raw field.
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
        self.log.debug('SplunkSearch: Processing splunk search results')
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
                        'summary': dps.get(summary_field or '_raw', 'Field {} not found in returned record'.format(text_field) ),
                        'message': "%r" % dps,
                        'eventClass': datasource.eventClass,
                        'eventKey': self.event_class_key,
                        'severity': datasource.severity,
                        })

        self.log.debug('SplunkSearchEvent: TO_RETURN: {}'.format(to_return))

        return to_return


class UGELast(SplunkQuery):
    """Collects LastSubmitted, LastStarted and LastCompleted times from a UGE environment using splunk

       The splunk query should return one row with the 3 fields included.  The text of these fields
       will be stored in corresponding attributes of the device

       eg.
       Query:
          index=* sourcetype=uge_accounting submission_time!=0 owner!=root | eval last_job_submission=strftime(submission_time, "%F %T.%3N") |
            stats max(last_job_submission) by index | rename max(last_job_submission) as "LastSubmission" |
            appendcols [search index=* sourcetype=uge_accounting submission_time!=0 owner!=root | eval last_job_start=strftime(start_time, "%F %T.%3N") |
                          stats max(last_job_start) by index | rename max(last_job_start) as "LastStarted"] |
            appendcols [search index=* sourcetype=uge_accounting submission_time!=0 failed=0  owner!=root |
                          eval last_job_end=strftime(end_time, "%F %T.%3N") | stats max(last_job_end) by index | rename max(last_job_end) as "LastEnded"]
       Results:
          {"fields": [{"name": "index", "groupby_rank": "0"}, {"name": "LastSubmission"}, {"name": "LastEnded"}, {"name": "LastStarted"}],
           "messages": [{"text": "Your timerange was substituted based on your search string", "type": "INFO"},
                        {"text": "[subsearch]: Your timerange was substituted based on your search string", "type": "INFO"}],
           "results": [{"index": "seis", "LastSubmission": "2016-08-31 10:50:24.000", "LastStarted": "2016-08-31 10:50:33.000", "LastEnded": "2016-08-31 10:51:30.000"},
                       {"index": "viz", "LastSubmission": "2016-08-31 10:48:23.000", "LastStarted": "2016-08-31 10:48:23.000", "LastEnded": "2016-08-31 10:50:37.000"}],
           "highlighted": {},
           "preview": false,
           "init_offset": 0}
    """

    @classmethod
    def params(cls, datasource, context):
        return {
                'zSplunkServer': context.zSplunkServer,
                'zSplunkPort': context.zSplunkPort,
                'zSplunkUsername': context.zSplunkUsername,
                'zSplunkPassword': context.zSplunkPassword,
                'zSplunkTimeout': context.zSplunkTimeout,
                'splunkSearch': datasource.talesEval(datasource.splunkSearch, context),
                'tzoffset': datasource.tzoffset
                }

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        self.log.info('UGELast: Processing splunk search results')
        to_return = self.new_data()


        now = datetime.now()
        for datasource in config.datasources:
            try:
                tzoffset = float(datasource.params['tzoffset'])
            except ValueError:
                tzoffset = 0.0
            result = results.get(datasource.params['splunkSearch'], {})
            for dps in result.get('results', []):
                # result will have a list of dicts with 'index' being the UGE environment
                # and the remaining items being the search result column/value pairs
                if dps.get('index', None) == datasource.device:
                    objMap = ObjectMap()
                    objMap.lastSubmission = dps['LastSubmission']
                    objMap.lastStarted = dps['LastStarted']
                    objMap.lastEnded = dps['LastEnded']
                    to_return['maps'].append(objMap)
                    # Process requested datapoints
                    for datapoint_id in (x.id for x in datasource.points):
                        if datapoint_id not in dps:
                            continue

                        dpname = '_'.join((datasource.datasource, datapoint_id))

                        dtstr = dps[datapoint_id]
                        dtobj = datetime.strptime(dtstr, "%Y-%m-%d %X.%f")
                        dtdelta = now - dtobj

                        to_return['values'][datasource.component][dpname] = ((dtdelta.total_seconds() / 3600) + tzoffset, 'N')

        to_return = super(UGELast, self).onSuccess(to_return, config)

        self.log.debug('UGELast: TO_RETURN: {}'.format(to_return))

        return to_return


class HPCNodeStatus(SplunkQuery):
    """Collects counts of messages that match supplied search
    """

    @classmethod
    def params(cls, datasource, context):
        return {
                'zSplunkServer': context.zSplunkServer,
                'zSplunkPort': context.zSplunkPort,
                'zSplunkUsername': context.zSplunkUsername,
                'zSplunkPassword': context.zSplunkPassword,
                'zSplunkTimeout': context.zSplunkTimeout,
                'splunkSearch': datasource.talesEval(datasource.splunkSearch, context),
                'compPath': '/'.join(context.getMetricMetadata()['contextKey'].split('/')[2:])
                }

    def onSuccess(self, results, config):
        """Method to process results after a successful collection.
        """
        self.log.info('HPCNodeStatus: Processing splunk search results')
        to_return = self.new_data()

        resultsdicts = {}
        qassoc = defaultdict(list)
        for search, result in results.iteritems():
            resultsdict = {}
            for fields in result.get('results', []):
                if fields.get('index', "") != config.datasources[0].device:
                    continue
                resultsdict[fields.get('hostname', "")] = fields
                qassoc[fields.get('queue', "")].append(fields.get('hostname', ""))
            resultsdicts[search] = resultsdict

        for queue, nodes in qassoc.iteritems():
            objMap = ObjectMap()
            objMap.modname = 'ZenPacks.zenoss.PS.SA.UGE.UGEQueue'
            objMap.compname = 'ugequeues/{}'.format(prepId(queue))
            objMap.setNodes = nodes
            to_return['maps'].append(objMap)

        relname = 'hpcnodes'
        modname = 'ZenPacks.zenoss.PD.SA.UGE.HPCNode'
        for datasource in config.datasources:
            result = resultsdicts.get(datasource.params['splunkSearch'], {})
            dps = result.get(datasource.component, {})
            state = dps.get('state', 'Unknown')
            severity, state_string = {
                        'Ok': (0, "Ok"),
                        'a': (4, "Alarm"),
                        'd': (3, "Disabled"),
                        'u': (4, "Unreachable"),
                        'ad': (3, "Alarm, Disabled"),
                        'au': (4, "Alarm, Unreachable"),
                        'du': (3, "Disabled, Unreachable"),
                        'adu': (3, "Alarm, Disabled, Unreachable"),
                        'aduE': (5, "Major Issue"),
                        'Unknown': (4, "No State Received")
                       }.get(state, (4, "Unknown State"))
            message = "Status of Node is '{}'({})".format(state_string, state)
            eventClassKey = "UGE_Node_Status"
            event = {
                     'device': datasource.device,
                     'summary': message,
                     'component': datasource.component,
                     'eventClass': datasource.eventClass,
                     'eventGroup': 'UGE',
                     'severity': severity,
                     'eventClassKey': eventClassKey,
                    }
            to_return['events'].append(event)
            compname = '/'.join(datasource.params['compPath'].split('/')[:-2])
            objMap = ObjectMap()
            objMap.id = datasource.component
            objMap.relname = relname
            objMap.modname = modname
            objMap.compname = compname
            objMap.status = "{} ({})".format(state_string, state)
            to_return['maps'].append(objMap)

        to_return = super(HPCNodeStatus, self).onSuccess(to_return, config)

        self.log.debug('HPCNodeStatus: TO_RETURN: {}'.format(to_return))

        return to_return
