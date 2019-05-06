import re

from typing import List
from enum import Enum

import requests
from siphon.catalog import TDSCatalog


def is_opendap_url(url):
    if url and not url.startswith("file"):
        r = requests.get(url + ".dds")
        if r.status_code == 200 and r.content.decode().startswith("Dataset"):
            return True
    return False


class ParsingMethod(Enum):
    # parse the filename directly (faster and simpler, more likely to fail)
    filename = 1
    # parse each Data Attribute Structure (DAS) by appending .das to the url
    # One request for each dataset, so lots of small requests to the Thredds server
    opendap_das = 2
    # open the dataset using xarray and look at the file attributes
    # safer, but slower and lots of small requests are made to the Thredds server
    xarray = 3


def get_bcca2v2_opendap_datasets(
    catalog_url, variable, rcp, method: ParsingMethod = ParsingMethod.filename
) -> List[str]:
    """Get a list of urls corresponding to variable and rcp on a Thredds server.

    We assume that the files are named in a certain way on the Thredds server.

    This is the case for boreas.ouranos.ca/thredds
    For more general use cases, see the `xarray` and `requests` methods below."""
    catalog = TDSCatalog(catalog_url)

    urls = []

    for dataset in catalog.datasets.values():
        opendap_url = dataset.access_urls["OPENDAP"]

        if method == ParsingMethod.filename:
            if rcp in dataset.name and dataset.name.startswith(variable):
                urls.append(opendap_url)

        elif method == ParsingMethod.opendap_das:
            re_experiment = re.compile(r'String driving_experiment_id "(.+)"')
            lines = requests.get(opendap_url + ".das").content.decode().split("\n")

            has_variable = any(line.startswith(f"    {variable} {{") for line in lines)
            is_good_rcp = False
            for line in lines:
                match = re_experiment.search(line)
                if match and rcp in match.group(1).split(","):
                    is_good_rcp = True

            if has_variable and is_good_rcp:
                urls.append(opendap_url)

        elif method == ParsingMethod.xarray:
            import xarray as xr

            ds = xr.open_dataset(opendap_url, decode_times=False)
            rcps = [r for r in ds.attrs.get('driving_experiment_id', '').split(',') if 'rcp' in r]
            if rcp in rcps and variable in ds.data_vars:
                urls.append(opendap_url)

    return urls