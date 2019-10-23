#!/usr/bin/env python

"""
Python 3.x CLI for validating extension description files.
"""

import argparse
import os
import sys
import textwrap
import urllib.parse as urlparse

from functools import wraps


class ExtensionCheckError(RuntimeError):
    """Exception raised when a particular extension check failed.
    """
    def __init__(self, extension_name, check_name, details):
        self.extension_name = extension_name
        self.check_name = check_name
        self.details = details

    def __str__(self):
        return self.details


def require_metadata_key(metadata_key):
    check_name = "require_metadata_key"

    def dec(fun):
        @wraps(fun)
        def wrapped(*args, **kwargs):
            extension_name = args[0]
            metadata = args[1]
            if metadata_key not in metadata.keys():
                raise ExtensionCheckError(extension_name, check_name, "%s key is missing" % metadata_key)
            return fun(*args, **kwargs)
        return wrapped
    return dec


def parse_s4ext(ext_file_path):
    """Parse a Slicer extension description file.
    :param ext_file_path: Path to a Slicer extension description file.
    :return: Dictionary of extension metadata.
    """
    ext_metadata = {}
    with open(ext_file_path) as ext_file:
        for line in ext_file:
            if not line.strip() or line.startswith("#"):
                continue
            fields = [field.strip() for field in line.split(' ', 1)]
            assert(len(fields) <= 2)
            ext_metadata[fields[0]] = fields[1] if len(fields) == 2 else None
    return ext_metadata


@require_metadata_key("scmurl")
def check_scmurl_syntax(extension_name, metadata):
    check_name = "check_scmurl_syntax"

    if "://" not in metadata["scmurl"]:
        raise ExtensionCheckError(extension_name, check_name, "scmurl do not match scheme://host/path")

    supported_schemes = ["git", "https", "svn"]
    scheme = urlparse.urlsplit(metadata["scmurl"]).scheme
    if scheme not in supported_schemes:
        raise ExtensionCheckError(
            extension_name, check_name,
            "scmurl scheme is '%s' but it should by any of %s" % (scheme, supported_schemes))

@require_metadata_key("scm")
def check_scm_notlocal(extension_name, metadata):
    check_name = "check_scm_notlocal"
    if metadata["scm"] == "local":
        raise ExtensionCheckError(extension_name, check_name, "scm cannot be local")

@require_metadata_key("scmurl")
@require_metadata_key("scm")
def check_git_repository_name(extension_name, metadata):
    """See https://www.slicer.org/wiki/Documentation/Nightly/Developers/FAQ#Should_the_name_of_the_source_repository_match_the_name_of_the_extension_.3F
    """
    check_name = "check_git_repository_name"

    if metadata["scm"] != "git":
        return

    repo_name = os.path.splitext(urlparse.urlsplit(metadata["scmurl"]).path.split("/")[-1])[0]

    if not repo_name.startswith("Slicer"):

        variations = [prefix + repo_name for prefix in ["Slicer-", "Slicer_", "SlicerExtension-", "SlicerExtension_"]]

        raise ExtensionCheckError(
            extension_name, check_name,
            textwrap.dedent("""
            extension repository name is '%s'. Please, consider changing it to 'Slicer%s' or any of
            these variations %s.
            """ % (
                repo_name, repo_name, variations)))


def main():
    parser = argparse.ArgumentParser(
        description='Validate extension description files.')
    parser.add_argument(
        "--check-git-repository-name", action="store_true",
        help="Check extension git repository name. Disabled by default.")
    parser.add_argument("/path/to/description.s4ext", nargs='*')
    args = parser.parse_args()

    checks = []

    if args.check_git_repository_name:
        checks.append(check_git_repository_name)

    """ Other checks
    """
    checks.append(check_scmurl_syntax)
    checks.append(check_scm_notlocal)    

    total_failure_count = 0

    file_paths = getattr(args, "/path/to/description.s4ext")
    for file_path in file_paths:
        extension_name = os.path.splitext(os.path.basename(file_path))[0]

        failures = []
 
        metadata = parse_s4ext(file_path)
        for check in checks:
            try:
                check(extension_name, metadata)
            except ExtensionCheckError as exc:
                failures.append(str(exc))

        if failures:
            total_failure_count += len(failures)
            print("%s.s4ext" % extension_name)
            for failure in set(failures):
                print("  %s" % failure)

    print("Checked %d description files: Found %d errors" % (len(file_paths), total_failure_count))
    sys.exit(total_failure_count)


if __name__ == "__main__":
    main()
