ncagg: Aggregate NetCDF files
=================================

So... You want to aggregate NetCDF files? Ncagg is software that enables you to combine multiple
input NetCDF files into a single output NetCDF file.

* For interactive use: :ref:`cli`.
* For programatic use: :meth:`ncagg.aggregator.aggregate`.

Advanced users may want to familiarize themselves with :ref:`templates`.

:mod:`ncagg` features
......................

* aggregate files along unlimited dimensions
* insert fill values in gaps
* deduplicate records 
* sort a dimension by an indexing variable
* resolve global attributes according to a variety of strategies
* subset variables and dimensions
* create new dimensions variables in each input file variables with no existing unlimited dimension

This software was developed for the situation we faced with GOES-R series satellite data. We receive
data in small "granules", where each granule is a NetCDF file containing several seconds or minutes
of data. This format is very cumbersome for analysis, requiring thousands of file system operations
just to read a single day of data. Using ncagg we can combine these small NetCDF files into a single
dayfile for easier use. Often, we also create larger aggregations, a single file containing the
entire year, or even mission.


Or, perhaps you have daily model result files over a month,
and analysis is going to be easier if you could just
operate on a single file.


.. toctree::
   :maxdepth: 4
   :caption: Contents:

   cli
   template
   ncagg


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
