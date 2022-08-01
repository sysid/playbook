# Playbook

[![PyPI Version][pypi-image]][pypi-url]
[![Build Status][build-image]][build-url]
[![Code Coverage][coverage-image]][coverage-url]

> Define workflows as Playbooks and combine manual work tasks with automation.


`pip3 install playbook`

Define your own Playbook in a class extending from `Playbook`.

Every method that
doesn't begin with an underscore is read in as a step to be completed, in order.
The step name will be built from the method name, and the description is taken
either from the method's own docstring or from any data returned from invoking
the method.

Every Step can have attributes:

        * `repeatable` – step can be repeated when resuming or re-running playbook
        * `skippable` – step can be skipped by answering no, no justification needed
        * `critical` – step cannot be skipped and must be confirmed
        * `name` – alternative title for the step

```python
from playbook import Playbook


class CustomPlaybook(Playbook):

    def first_step(self):
        """
        Do ABC now.
        """
    def second_step(self):
        """
        Do EFG then wait 1 hour.
        """
    def third_step(self):
        task = "reboot"
        return f"perform a {task}"

    @staticmethod
    def last_step():
        """Everything ok?"""
```

Every `Playbook` object comes with a default main method that you can use to execute the script.

```python
if __name__ == '__main__':
    CustomPlaybook.main()
```

The run-book object can also be instantiated and run directly.

```python
book = CustomPlaybook(file_path="path/to/file")
book.run()
```

**You should avoid using the step names `run` and `main`**, which are already defined. If you need to override these
methods to define custom behavior then that is fine.

## Re-run
As steps are completed, the results are written out to a log file. You can set a custom log file path by passing
an argument to main, as in:

```
python3 my_playbook.py output.log
```

When reusing the same log file, already completed steps will be skipped. Any new steps found in the `Playbook`
and not already in the log will be processed as normal, with results appended to the end of the file.


## Previous Work
Inspired by [this blog post](https://blog.danslimmon.com/2019/07/15/do-nothing-scripting-the-key-to-gradual-automation)
by Dan Slimmon and [runbook](https://github.com/UnquietCode/runbook.py).


## Changelog
[CHANGELOG.md](CHANGELOG.md)


### License
Licensed under the Apache Software License 2.0 (ASL 2.0).


<!-- Badges -->

[pypi-image]: https://badge.fury.io/py/playbook.svg
[pypi-url]: https://pypi.org/project/playbook/
[build-image]: https://github.com/sysid/playbook/actions/workflows/build.yml/badge.svg
[build-url]: https://github.com/sysid/playbook/actions/workflows/build.yml
[coverage-image]: https://codecov.io/gh/sysid/playbook/branch/master/graph/badge.svg
[coverage-url]: https://codecov.io/gh/sysid/playbook
