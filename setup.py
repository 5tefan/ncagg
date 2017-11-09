from setuptools import setup
try:
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()

setup(
    name='ncagg',
    version='0.3.3',
    description="Utility for aggregation of NetCDF data.",
    author="Stefan Codrescu",
    author_email="stefan.codrescu@noaa.gov",
    url="https://ctor.space/gitlab/work/ncagg",
    packages=["ncagg"],
    long_description=read_md('README.md'),
    install_requires=[
        'cerberus',
        'Click',
        'numpy',
        'netCDF4'
    ],
    entry_points='''
        [console_scripts]
        ncagg=ncagg.cli:cli
        template-ncagg=ncagg.cli_template:cli_template
    ''',
    include_package_data=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)
