# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spack.package import *


class PyRepligit(PythonPackage):
    """A Git client for mirroring multiple remotes without storing state."""

    homepage = "https://github.com/LLNL/repligit"
    git = "git@github.com:LLNL/repligit.git"

    maintainers("alecbcs", "cmelone")

    license("Apache-2.0 WITH LLVM-exception")

    version("main", branch="main")

    depends_on("py-hatchling", type="build")

    depends_on("py-requests", type=("build", "run"))
