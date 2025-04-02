# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack.package import *


class PyRepligit(PythonPackage):
    """A Git client for mirroring multiple remotes without storing state."""

    homepage = "https://github.com/LLNL/repligit"
    git = "https://github.com/LLNL/repligit.git"

    maintainers("alecbcs", "cmelone")

    license("Apache-2.0 WITH LLVM-exception")

    version("main", branch="main")

    variant("aiohttp", default="False", description="Enable aiohttp support")

    depends_on("py-hatchling", type="build")

    depends_on("py-aiohttp", type=("build", "run"), when="+aiohttp")
