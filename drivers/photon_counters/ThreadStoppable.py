import threading
import queue

class ThreadStoppable(object):
    def __init__(self, target_to_loop, timeout=-1, args=()):
        self._target_to_loop = target_to_loop
        self._args = args
        self._timeout = timeout
        self.queue = queue.Queue()

        self.start()

    def loop(self):
        while not self._stop_loop:
            r = self._target_to_loop(*self._args)
            self.queue.put(r)

    def stop(self):
        self._stop_loop = True

    def start(self):
        self._stop_loop = False
        self.thread = threading.Thread(target=self.loop)
        self.thread.start()

        assert self._timeout > 0 or self._timeout == -1, \
                'Invalid timeout value given.'
        if self._timeout > 0:
            t = threading.Timer(self._timeout, self.stop)
            t.start()

