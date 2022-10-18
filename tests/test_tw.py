from src.playbook import Playbook


class CustomPlaybook(Playbook):
    """
    This playbook is a basic example that exercises
    the various options available.
    """

    def first_step(self):
        """
        Do ABC now.
        """

    def second_step():
        """Do EFG then wait 1 hour."""

    def third_step(self, skippable=False, critical=True):
        value = "string"
        return f"a custom {value}"

    def third_step2(self, skippable=True, critical=False):
        value = "string"
        return f"a custom {value}"

    def last_step(name="the end"):
        pass


if __name__ == "__main__":
    CustomPlaybook.main()
