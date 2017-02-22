import click
import json
import netCDF4 as nc
import numpy as np


def init_config_template(sample_netcdf):
    with nc.Dataset(sample_netcdf) as nc_in:
        config = {"global attributes": {k: {"type": "constant", "value": nc_in.getncattr(k)} for k in nc_in.ncattrs()},
                  "data variables": {k: {
                      "fill value": getattr(nc_in.variables[k], "_FillValue", np.float32(-99999)).item(),
                      "include": True,
                      "override": None,
                  } for k in nc_in.variables.keys()}}
        return config


@click.command()
@click.argument("sample_netcdf", type=click.Path(exists=True), help="Sample file to create aggregation config from.")
def cli_init_config_template(sample_netcdf):
    click.echo(json.dumps(init_config_template(click.format_filename(sample_netcdf)), sort_keys=True, indent=4))


if __name__ == "__main__":
    cli_init_config_template()

