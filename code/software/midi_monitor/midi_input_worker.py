"""Threaded, non-blocking USB MIDI input for the desktop monitor."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any


class MidiInputWorker:
    """Own one mido input port and forward messages to a thread-safe queue.

    The worker deliberately opens, polls, and closes the RtMidi port on the
    same background thread.  Tk's main thread therefore never waits inside a
    driver call, including when the application window is being closed.
    """

    def __init__(
        self,
        backend: Any,
        device_name: str,
        output_queue: queue.Queue[tuple[str, object]],
        poll_interval_seconds: float = 0.005,
        heartbeat_seconds: float = 1.0,
    ) -> None:
        self.backend = backend
        self.device_name = device_name
        self.output_queue = output_queue
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("MIDI input worker can only be started once")
        self._thread = threading.Thread(
            target=self._run,
            name="midi-input-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Request shutdown without waiting for the MIDI driver."""

        self._stop_event.set()

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        input_port: Any = None
        try:
            input_port = self.backend.open_input(self.device_name)
            self.output_queue.put(("receiver_connected", self))
            last_heartbeat = time.monotonic()

            while not self._stop_event.is_set():
                message = input_port.poll()
                if message is not None:
                    self.output_queue.put(("receiver_message", (self, message)))
                    continue

                now = time.monotonic()
                if now - last_heartbeat >= self.heartbeat_seconds:
                    self.output_queue.put(("receiver_heartbeat", self))
                    last_heartbeat = now
                self._stop_event.wait(self.poll_interval_seconds)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.output_queue.put(("receiver_error", (self, str(exc))))
        finally:
            if input_port is not None:
                try:
                    input_port.close()
                except Exception:
                    pass
            self.output_queue.put(("receiver_stopped", self))
