"""Build the portable Python package using Poetry as the metadata source."""
from pathlib import Path

from poetry.core.factory import Factory
from setuptools import find_packages, setup

package = Factory().create_poetry(Path(__file__).parent).package

setup(
    name=package.pretty_name,
    version=package.pretty_version,
    description=package.description,
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author=", ".join(package.authors),
    license=package.license.id,
    python_requires=str(package.python_constraint),
    packages=find_packages(include=["tachyon_api", "tachyon_api.*"]),
    install_requires=[d.to_pep_508() for d in package.requires if not d.is_optional()],
    extras_require={
        name: [d.to_pep_508(with_extras=False) for d in dependencies]
        for name, dependencies in package.extras.items()
    },
    entry_points={
        "console_scripts": [
            f"{name}={target}"
            for name, target in package.entry_points.get("console-scripts", {}).items()
        ]
    },
    include_package_data=False,
)
