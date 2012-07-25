===============================================================================
ZenPacks.zenoss.Splunk
===============================================================================


About
===============================================================================

Splunk is a search engine for IT data. It lets you search and analyze all the
data your IT infrastructure generates from a single location in real time. More
information on Splunk can be found online at http://www.splunk.com/.

The Splunk ZenPack allows you to monitor the results of a Splunk search. The
total count returned by a search can be recorded, thresholded and graphed as
well as additional tabular data contained within the results of more advanced
searches that make use of Splunk's top filter. The value of monitoring Splunk
searches is that it adds an easy and flexible way to monitor log data at
aggregate level instead of on a log-by-log basis.


Features
-------------------------------------------------------------------------------

The Splunk ZenPack provides:

* A new *Splunk* data source type that allows Zenoss to threshold on, store,
  and graph the results of Splunk searches.


Prerequisites
-------------------------------------------------------------------------------

==================  ========================================================
Prerequisite        Restriction
==================  ========================================================
Zenoss Platform     3.0 and later
Zenoss Processes    zencommand
Installed ZenPacks  ZenPacks.zenoss.Splunk
Firewall Acccess    Collector server to 8089/tcp of Splunk server
Splunk Server       Splunk version 3 and 4
==================  ========================================================


Usage
===============================================================================


Installation
-------------------------------------------------------------------------------

This ZenPack has no special installation considerations. You should install the
most recent version of the ZenPack for the version of Zenoss you're running.

* `Packages for Zenoss 4.2`_
* `Packages for Zenoss 4.1`_
* `Packages for Zenoss 4.0`_
* `Packages for Zenoss 3.2`_

.. _Packages for Zenoss 4.2: http://zenpacks.zenoss.com/pypi/github/4.2/ZenPacks.zenoss.Splunk
.. _Packages for Zenoss 4.1: http://zenpacks.zenoss.com/pypi/github/4.1/ZenPacks.zenoss.Splunk
.. _Packages for Zenoss 4.0: http://zenpacks.zenoss.com/pypi/github/4.0/ZenPacks.zenoss.Splunk
.. _Packages for Zenoss 3.2: http://zenpacks.zenoss.com/pypi/github/3.2/ZenPacks.zenoss.Splunk

To install the ZenPack you must copy the ``.egg`` file to your Zenoss master
server and run the following command as the ``zenoss`` user::

    zenpack --install <filename.egg>

After installing you must restart Zenoss by running the following command as
the ``zenoss`` user on your master Zenoss server::

    zenoss restart

If you have distributed collectors you must also update them after installing
the ZenPack.


Splunk Data Source Type
-------------------------------------------------------------------------------

The Splunk ZenPack adds the new Splunk data source type to your Resource Manager
system. This data source can be used to monitor the results of Splunk searches.

The Splunk data source type has the following fields in common with many other
Resource Manager data source types.

* *Name*: The name given to your data source.
* *Enabled*: This data source will only be polled if enabled is set to true.

In the event that the Splunk search fails to execute successfully an event will
be generated. The following fields control key fields in the generated event. It
is important to note that these fields only apply when the Splunk search fails
to execute, and not when a threshold on the data point is breached.

* *Component*
* *Event Class*
* *Event Key*
* *Severity*

The following fields are specific to Splunk type data sources.

* *Splunk Server*: Hostname or IP address of your Splunk server. If left blank
  the ``SPLUNK_SERVER`` environment variable will be used.

* *Splunk Port*: Port that the splunkd daemon is listening on. Default is
  ``8089``. If left blank the ``SPLUNK_PORT`` environment variable will be
  used.

* *Splunk Username*: Default is admin. If left blank the ``SPLUNK_USERNAME``
  environment variable will be used.

* *Splunk Password*: Default is changeme. If left blank the ``SPLUNK_PASSWORD``
  environment variable will be used.

* *Search*: Search string exactly as it would be typed into the Splunk search
  engine. Be careful to use full quotes and not apostrophes where necessary.

.. note::
    Username and password should be left blank when using the free version of
    Splunk. See the following Splunk documentation for `configuring your free
    Splunk server for remote administration`_.

.. _configuring your free Splunk server for remote administration:
    http://docs.splunk.com/Documentation/Splunk/latest/Admin/AccessandusetheCLIonaremoteserver


Monitoring Splunk Searches
-------------------------------------------------------------------------------


Monitoring Results of a Simple Search
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to get started monitoring your Splunk searches is with a simple
search. The following steps will illustrate a simple way to build dynamic Splunk
search monitoring.

This example demonstrates how to detect brute-force password cracking attempts
on all Linux servers.

1. Build a search in Splunk to verify that you're getting the expected data.
   This example shows a query of ``host="zendev.damsel.loc" minutesago=5 "failed password"``.

.. note::
   Using a time specifier such as ``minutesago=5`` within your search can be
   a useful trick when it comes to monitoring searches from Resource Manager. We
   will have Resource Manager automatically replace zendev.damsel.loc with the
   appropriate hostname using a ``${here/id}`` TALES expression.

2. Create a Resource Manager monitoring template for monitoring this Splunk
   search.

    1. From Advanced > Monitoring Templates, click + to add a monitoring
       template.

    2. Enter ``SplunkLinux`` in the *Name* field and select */Service/Linux*
       for *Template Path*, and then click submit.

    3. Select the newly created template.

    4. Add a Splunk data source to capture the count of failed passwords.

        1. In the Data Sources area, click + to add a data source.

        2. In the Add Data Source dialog, set the *Name* to ``failedPassword``
           and the *Type* to *Splunk*, and then click OK.

        3. Double-click the data source to configure it as follows, and then
           click save.

            * *Splunk Server*: Hostname or IP of your Splunk server
            * *Splunk Port*: ``8089``
            * *Splunk Username*: Splunk username (default is admin)
            * *Splunk Password*: Splunk password (default is changeme)
            * *Search*: ``host="${here/id}" minutesago=5 "failed password"``

        4. Add the count data point to the failedPassword data source.

            1. Select Add Data Point from the Data Sources Action menu.

            2. Set the *Name* to ``count`` and click OK.

        5. Add a threshold of how many failed passwords constitutes an attack.

            1. In the Thresholds area, click + to add a threshold.

            2. Set the *Name* to ``password attack`` and *Type* to
               *MinMaxThreshold*, and then click add.

            3. Select *failedPassword_count* from Data Points.

            4. Set the *Max Value* to ``10``.

            5. Set the *Event Class* to ``/Security/Login/BadPass``.

            6. Click save.

        6. Add a graph to visualize failed passwords per 5 minutes.

            1. In the Graph Definitions area, click + to add a graph.

            2. Set the Name to ``Splunk - Failed Passwords``, and then click
               submit.

            3. Double-click the newly created graph to edit it.

            4. Set the *Units* to ``failed/5min``.

            5. Set the *Min Y* to ``0``.

            6. Select *Manage Graph Points* from the Action menu in the Graph
               Definitions area.

            7. Select *Data Point* from the Add menu.

            8. Select *failedPassword_count* from Data Point, and then click
               submit.

            9. Click into the new *count* graph point.

            10. Set the *Format* to ``%6.1lf``.

            11. Set the *Legend* to ``Count``.

            12. Click save.

        7. Bind the *SplunkLinux* template to the */Server/Linux* device class.

            1. From Infrastructure > Devices, navigate to the */Server/Linux*
               device class.

            2. Click Details.

            3. Select *Bind Templates* from the Action menu.

            4. Move the *SplunkLinux* template from the Available area to the
               Selected area, and then click save.

Now you will have a Failed Passwords graph on all of your Linux servers that
visualizes how many failed password attempts have occurred over the last 5
minutes. You will also get a warning severity event anytime more than 10 failed
password attempts are made within a 5 minute period.


Monitoring Results of a Top Search
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Monitoring additional data points within a top search builds on monitoring a
simple search. You can extra numeric data from the tabular results returned from
a top search using the following steps.

This example demonstrates how you can monitor the logs by source type for all
Linux devices.

1. Build a search in Splunk to verify that you're getting the expected data.
   This example shows a query of ``host="zendev.damsel.loc" minutesago=5 | top sourcetype.``

.. note::
    Take special note of the names in the sourcetype column and the names of the
    count and percent columns. These will be used to construct the names of the
    datapoints within our Splunk data source.

2. Setup a Resource Manager monitoring template just as described in the simple
   search example.

3. Add a Splunk type data source named sourcetype to the template with the
   following settings.

    * *Splunk Server*: Hostname or IP of your Splunk server
    * *Splunk Port*: ``8089``
    * *Splunk Username*: Splunk username (default is admin)
    * *Splunk Password*: Splunk password (default is changeme)
    * *Search*: ``host="${here/id}" minutesago=5 | top sourcetype``

4. Add data points to the sourcetype data source with the following names.
   These names come from concatenating the data in the first column of each row
   with the name of the column name with the target numeric data.

    * ``linux_audit_count``
    * ``linux_audit_percent``
    * ``linux_secure_count``
    * ``linux_secure_percent``

5. Create a graph that will show these results within Resource Manager in a
   useful way.

    1. Add a graph from the Graph Definitions area of the monitoring template.

    2. Set the *ID* to ``Splunk - Logs by Source Type`` then click Submit.

    3. Set the *Units* to ``percent``.

    4. Set the *Min Y* to ``0``.

    5. Set the *Max Y* to ``100``.

    6. Click Save.

    7. Select Manage Graph Points from the Action menu in the Graph Definitions
       area.

    8. Select Data Point from the Add menu.

    9. Use SHIFT-click or CTRL-click to select the following data points from
       the list then click Submit.

        * ``sourcetype_linux_audit_percent``
        * ``sourcetype_linux_secure_percent``

    #. Click into each of the graph points you just added to the graph and set
       the following properties.

        * *Line Type*: Area
        * *Stacked*: True
        * *Format*: ``%5.1lf%%``
        * *Legend*: ``Audit`` or ``Secure`` respectively.

6. Bind the monitoring template to the */Server/Linux* device class just as in
   the simple search example.

You will now have a graph for all Linux devices that shows what percentage of
logs are coming from the audit and secure logs respectively. This ability to
track multiple results from a single Splunk search has many other possible uses.
Experiment with the top and stats filters in Splunk to see what other useful
data you can extract.


Removal
-------------------------------------------------------------------------------

This ZenPack has no special removal considerations. To remove this ZenPack you
must run the following command as the ``zenoss`` user on your master Zenoss
server::

    zenpack --remove ZenPacks.zenoss.Splunk

You must then restart the master Zenoss server by running the following command
as the ``zenoss`` user::

    zenoss restart
