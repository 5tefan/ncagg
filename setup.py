from setuptools import setup

setup(
    name='aggregoes',
    version='0.1',
    author="Stefan Codrescu",
    author_email="stefan.codrescu@noaa.gov",
    py_modules=['aggregoes'],
    install_requires=[
        'Click',
        'numpy',
        'netCDF4'
    ],
    entry_points='''
        [console_scripts]
        aggregoes=aggregoes.cli:cli
    ''',
    classifiers=[
        "Development Status :: 3 - Alpha",
    ]
)
