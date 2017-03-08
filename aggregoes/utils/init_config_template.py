import click
import json
import numpy as np
import netCDF4 as nc


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NumpyEncoder, self).default(obj)

# using lists across the generate config functions in order to
# preserve order.


def generate_default_global_attributes_config(an_input_file):
    with nc.Dataset(an_input_file) as nc_in:
        return [{
            "name": att,
            "strategy": "constant",
            "value": nc_in.getncattr(att)
        } for att in nc_in.ncattrs()]


def generate_default_dimensions_config(an_input_file):
    with nc.Dataset(an_input_file) as nc_in:
        return [{
            "name": dim.name,
            "size": None if dim.isunlimited() else dim.size,
            "index_by": None,
            "other_dim_indicies": {},
            "min": None,
            "max": None,
            "expected_cadence": {}
        } for dim in nc_in.dimensions.values()]


def generate_default_variables_config(an_input_file):
    with nc.Dataset(an_input_file) as nc_in:
        result =  [{
            "name": k,
            "dimensions": nc_in.variables[k].dimensions,
            "datatype": str(nc_in.variables[k].datatype),
            "attributes": {ak: nc_in.variables[k].getncattr(ak) for ak in nc_in.variables[k].ncattrs()}
        } for k in nc_in.variables.keys()]

        # If the variable doesn't come with an explicit fill value, set it to the netcdf.default_fillvals value
        # https://github.com/Unidata/netcdf4-python/blob/6087ae9b77b538b9c0ab3cdde3118b4ceb6f8946/netCDF4/_netCDF4.pyx#L3359
        for each in result:
            if "_FillValue" not in each["attributes"].keys():
                each["attributes"]["_FillValue"] = np.dtype(each["datatype"]).type(
                    nc.default_fillvals[np.dtype(each["datatype"]).str[1:]]
                )

        return result


def init_config_template(sample_netcdf):
    return {
        "global attributes": generate_default_global_attributes_config(sample_netcdf),
        "dimensions": generate_default_dimensions_config(sample_netcdf),
        "variables": generate_default_variables_config(sample_netcdf)
    }


@click.command()
@click.argument("sample_netcdf", type=click.Path(exists=True))
def cli_init_config_template(sample_netcdf):
    click.echo(json.dumps(
        init_config_template(click.format_filename(sample_netcdf)),
        sort_keys=True, indent=4, cls=NumpyEncoder
    ))


if __name__ == "__main__":
    cli_init_config_template()

