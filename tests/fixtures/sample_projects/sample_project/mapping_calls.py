class Dispatcher:
    def __init__(self):
        self._map = {'start': self.start, 'stop': self.stop}

    def start(self): return 'started'
    def stop(self): return 'stopped'

    def call(self, cmd):
        return self._map[cmd]()

def use_dispatcher(cmd):
    d = Dispatcher()
    return d.call(cmd)
