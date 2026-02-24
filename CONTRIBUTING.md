# Contributing to Swarm It

Thanks for your interest in contributing to Swarm It.

## Patent Notice

This project includes material that is the subject of one or more pending patent applications.
See [PATENT_NOTICE.md](PATENT_NOTICE.md) for details.

## License of Contributions

By submitting a contribution (pull request, patch, issue content, or code), you agree that:

1. **Ownership**: You have the right to submit the contribution and it does not violate any third-party rights.

2. **License Grant**: Your contribution is licensed under the same terms as this project's LICENSE file.

3. **Usage Rights**: You grant the project maintainer(s) the right to use, modify, sublicense, and distribute your contribution as part of the project.

## No Separate Patent License From Contributors

Unless stated otherwise in writing, contributors do not grant a separate patent license beyond what is included in the project LICENSE (if any) and applicable law.

## Developer Certificate of Origin (DCO)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/).

By signing off on your commits, you certify the DCO:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### How to Sign Off

Add a sign-off line to your commit messages:

```bash
git commit -s -m "Your commit message"
```

This adds:
```
Signed-off-by: Your Name <your@email.com>
```

## Code Standards

- Follow existing code style
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

## Line Endings (Cross-Platform)

To avoid whitespace conflicts between Windows and macOS/Linux:

- This repo enforces LF via `.gitattributes` and `.editorconfig`.
- On Windows, set `git config core.autocrlf false` in this repo.
- If you see line-ending churn, run `git add --renormalize .` once.

## Questions?

Open an issue for questions about contributing.
