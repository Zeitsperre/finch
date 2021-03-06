import logging
from multiprocessing.pool import ThreadPool
from pathlib import Path

from pywps import FORMATS
from pywps.inout.outputs import MetaLink4, MetaFile

from finch.processes.base import FinchProcess

LOGGER = logging.getLogger("PYWPS")


class SubsetProcess(FinchProcess):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def subset_resources(self, resources, subset_function, threads=1) -> MetaLink4:
        metalink = MetaLink4(
            identity="subset_bbox",
            description="Subsetted netCDF files",
            publisher="Finch",
            workdir=self.workdir,
        )

        def process_resource(resource):
            ds = self.try_opendap(resource)
            out = subset_function(ds)

            if not all(out.dims.values()):
                LOGGER.warning(f"Subset is empty for dataset: {resource.url}")
                return

            p = Path(resource._file or resource._build_file_name(resource.url))
            out_fn = Path(self.workdir) / (p.stem + "_sub" + p.suffix)

            out.to_netcdf(out_fn)

            mf = MetaFile(
                identity=p.stem,
                fmt=FORMATS.NETCDF,
            )
            mf.file = out_fn
            metalink.append(mf)

        if threads > 1:
            pool = ThreadPool(processes=threads)
            list(pool.imap_unordered(process_resource, resources))
        else:
            for r in resources:
                process_resource(r)

        return metalink
