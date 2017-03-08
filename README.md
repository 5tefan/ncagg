# GOES Aggregation (AggreGOES)

So... you want to aggregate GOES data? -- A utility to aggregate L1b and L2+ GOES Space Weather products.

## High level overview

Aggregation works in two stages:
1. Create an AggreList object.
2. Evaluate the AggreList object.

In Stage 1. a list of files and configuration information is given. From this, the Aggregator creates an
AggreList which contains all the information needed to perform the aggregation. Depending on how well
specified the configuration is, the AggreList may specify to Fill missing chunks or transoform the data.

Stage 2 is comparatively simple and consists of reading data from the AggreList into the final aggregated
output file.

## Configurations

There are two stages of configuration available to specify the output of aggregation:
1. Product configuration
2. Aggregation configuration

Type 1 - the product configuration is a high level description of the product to be aggregated.
It consists of three fields, "global attributes", "dimensions", and "variables". It is almost
like a json CDL for a netcdf, but with extensions customized for aggregation. This configuration
specifies how the output should look, how global attributes are handled. An intial configuration
can be initialized using a command line utility.

Type 2 - aggregation configuration contains information specific to generating a single output
file, and includes information indicating which variables index unlimited dimensions, what their
min and max values are, and what their expected cadences are.



The aggregoes tool is configuration based.

The top level Product Configuration specifies how global attributes and data variables
should be treated while aggregating a specific product. It is unlikely that the Product
Configuration will need to change once it is set for a product.

With a Product Configuration in place, there are several ways to produce aggregated files:

 - On systems with the standard NCEI /nfs/spades_inst_prod/ mount structure, start_time and
end_time are the only things required.
 - A lower level interface accepting a list of files, start time, end time, and configuration
is also available.

### Product Configuration



Ideas:
Recursive, if the input is determined to be too large to plan_aggregation, split into smaller
chunks, aggregate, and then aggregate the chunks.



Aggregator object is basically an instance of the configuration for aggregation of a product,
at initialization, only knows about how to aggregation.

Step 2, generate the AggreList object, must specify the aggregate output start and end time,
as well as a list of files.

Step 3. evaluate the AggreList to produce the aggregate output. All information to create the
aggregate file should be contained within the AggreList instance, no template file...



There must be at least one file in the list of files to aggregate.