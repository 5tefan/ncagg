.. _cli:

The CLI
======================

The Command Line Interface exposes ncagg as a command line
program capable of aggregating a list of files to an output file.

The usage message is given below:

.. click:: ncagg.cli:cli
   :prog: ncagg


Notes
......

The basic usage is modeled after the ``zip`` program. The first argument is the output
file, while the following specify the contents.


.. code:: bash

    ncagg output.nc input1.nc input2.nc

If aggregating so many files that the system limits on command length are met, ``ncagg``
can also take the list of files to aggregate from stdin.

.. code:: bash

    find . -type f -name "*.nc" | ncagg output.nc

Unlimited Dimension Config
..........................

An Unlimited Dimension Config specifies sorting capabilities: Given a dataset with
an unlimited dimension called "report_number", and a variable time that is a function
of report_number, ie. time(report_number), the following argument would configure 
``ncagg`` to sort report_number according to time when it aggregates.

.. code:: bash

    -u report_number:time

Furthermore, if one expects apriori for a report_number to occur every second, the
frequency can be specified (in units of hz). This configuration will deduplicate 
overlapping record and insert records is a gap is detected:

.. code:: bash

    -u report_number:time:1

Aggregation Boundaries
......................

*IF* an Unlimited Dimension Config is given, boundaries can additionally be imposed
in the form min:max:

.. code:: bash

   -b 0:10

By default, these are expected to in the same units as the UDC ivar, however, when
dealing with time, often these values have units inconvenient to humans such as 
seconds since j2k. For convenience, the bounds can be specified in Tstart:Tstop 
format where start and stop are YYYY[MM[DD[HH[MM]]]]. If only start is given,
stop will be inferred to be one increment of the least significantly specified date
component.

The following would create a dayfile for 2018 03 30

.. code:: bash

   -b T20180330

A half day could be done like this:

.. code:: bash

   -b T20180330:T2018033012


A note on templates
...................

No template is required to perform aggregation. Template usage is considered advanced.
See :ref:`templates` for complete information. 

Template syntax is verbose json. It is inconceivable that a human would create a 
template from scratch. Instead, one should modify a default template. The way to 
do this using ncagg would be:

.. code:: bash

   ncagg --generate_template input1.nc > template.json

Then modify the template and perform aggregation usint it:

.. code:: bash

   ncagg -t template.json output.nc input1.nc input2.nc



