from setuptools import setup, find_packages

setup(
    name='aggregoes',
    version='0.1',
    author="Stefan Codrescu",
    author_email="stefan.codrescu@noaa.gov",
    packages=find_packages(),
    install_requires=[
        'Click',
        'numpy',
        'netCDF4'
    ],
    entry_points='''
        [console_scripts]
        aggregoes=aggregoes.cli:cli
        ncei-l1b-cli=aggregoes.ncei.ncei_l1b_cli:cli
    ''',
    include_package_data=True,
    package_data={
        # https://setuptools.readthedocs.io/en/latest/setuptools.html#including-data-files
        # If any package contains *.json, include them:
        '': ['*.json'],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
    ]
)
