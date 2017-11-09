import click
import json

from config import Config

@click.command()
@click.argument("sample_netcdf", type=click.Path(exists=True))
def cli_template(sample_netcdf):
    the_config = Config.from_nc(click.format_filename(sample_netcdf)).to_dict()
    click.echo(json.dumps(the_config, sort_keys=True, indent=4))

if __name__ == "__main__":
    cli_template()

