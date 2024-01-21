from setuptools import setup


setup(
    name="ncagg",
    version="0.8.18",
    description="Utility for aggregation of NetCDF data.",
    author="Stefan Codrescu",
    author_email="stefan.codrescu@noaa.gov",
    url="https://github.com/5tefan/ncagg",
    packages=["ncagg"],
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    install_requires=["cerberus", "click", "numpy", "netCDF4"],
    entry_points="""
        [console_scripts]
        ncagg=ncagg.cli:cli
    """,
    include_package_data=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Documentation": "http://ncagg.readthedocs.io/en/latest/",
    },
)
