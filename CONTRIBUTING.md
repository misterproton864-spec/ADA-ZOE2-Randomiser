# Contributing

Open an Issue before a substantial feature or behavioural change. For fixes, create a branch and submit a pull request explaining the failure, the changed behaviour and the checks performed.

Work from the published Local.22 source snapshot. Do not silently mix unfinished Local.23 changes into this release. Preserve seed reproducibility, input identity checks, transactional Apply/Restore and the boss/arena rules documented by the project.

Run `python tools/audit_repository.py` before submitting. Use targeted regression checks for the behaviour being changed. Game-dependent tests must use your own legitimate installation and isolated working copies; never commit those copies, generated seeds, original-file caches, game assets or private reports. A startup or static check is not evidence that a boss encounter can be completed.

Report whether a fix was checked offline, in live gameplay, or both. Include seed/options and the affected mode/arena. Contributions to original ADA code are accepted under this repository's MIT licence. Retain third-party notices.
