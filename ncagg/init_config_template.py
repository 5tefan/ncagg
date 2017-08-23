import click
import json

from ncagg.config import Config

@click.command()
@click.argument("sample_netcdf", type=click.Path(exists=True))
def cli_init_config_template(sample_netcdf):
    click.echo(json.dumps(
        Config.from_nc(click.format_filename(sample_netcdf)),
        sort_keys=True, indent=4
    ))

if __name__ == "__main__":
    cli_init_config_template()

