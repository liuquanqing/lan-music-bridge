# Release checklist

This repository may be pushed only from a clean release tree.

1. Confirm `PROVENANCE.md`, `NOTICE`, and dependency status are current.
2. Confirm no provider SDK, wheel, bytecode, media, firmware, runtime database,
   household configuration, credential, signed URL, device identity, or private
   adapter is present.
3. Run `make check` and `make release-audit` from the repository root.
4. Review `git status --short`, `git diff --check`, and the exact staged file list.
5. Record the exact commit SHA before an external push.
6. Create the GitLab project only after visibility, namespace, name, license, and
   provenance are reviewed.
7. Push the default branch, then read back remote visibility, branch, commit SHA, and
   CI status. A successful transport alone is not release acceptance.

This checklist covers an initial repository push. Publishing a tag, Release, package,
container, or registry artifact is a separate external action and requires its own
authorization and provenance receipt.
