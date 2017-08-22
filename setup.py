from setuptools import setup

setup(
    name='ncagg',
    version='0.2',
    author="Stefan Codrescu",
    author_email="stefan.codrescu@noaa.gov",
    packages=["ncagg"],
    install_requires=[
        'cerberus',
        'Click',
        'numpy',
        'netCDF4'
    ],
    entry_points='''
        [console_scripts]
        ncagg=ncagg.cli:cli
    ''',
    include_package_data=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)
