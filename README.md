# GOES Aggregation

Utility to aggregate L1b and L2+ GOES Space Weather products.

## Configuration

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

