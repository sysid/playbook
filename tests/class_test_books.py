from src.playbook import Playbook


class BookA(Playbook):
    """
    Preamble
    """

    def step_b1():
        pass


class BookB(Playbook):
    def step_a2(self):
        pass

    @staticmethod
    def step_a3():
        pass
