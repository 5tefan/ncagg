ncagg: Aggregate NetCDF files
=================================

So... You want to aggregate NetCDF files?

* For interactive use: :ref:`cli`.
* For programatic use: :meth:`ncagg.aggregator.aggregate`.

Advanced users may want to familiarize themselves with :ref:`templates`.

:mod:`ncagg` features
......................

* aggregate files along unlimited dimensions
* insert fill values in gaps
* deduplicate observations 
* sort a dimension by an indexing variable
* resolve global attributes according to a variety of strategies
* subset variables and dimensions
* create dimensions for per file variables with no unlimited dimension

Imagine you receive data in NetCDF files, except
that every file has just 30 seconds of data. You're
looking at 2880 files per day, but you just want
**one** dayfile.

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
