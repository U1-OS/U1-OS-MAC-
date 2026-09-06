import time
import threading

class BaseService:
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.lock = threading.RLock()
        self.configured = False
        self.status = "unconfigured"
        self.missing_keys = []
        self.last_updated = 0
        self.data = {}
        self.recent_events = []
        self._event_counter = 0

    def add_event(self, event_type, summary, payload=None):
        with self.lock:
            self._event_counter += 1
            event = {
                "id": f"{self.name}-{int(time.time()*1000)}-{self._event_counter}",
                "timestamp": time.time(),
                "type": event_type,
                "summary": summary,
                "payload": payload or {}
            }
            self.recent_events.append(event)
            # Keep only the last 15 events
            if len(self.recent_events) > 15:
                self.recent_events.pop(0)
            return event

    def poll(self):
        """Called periodically by the feeder daemon."""
        raise NotImplementedError

    def dispatch_action(self, action, payload=None):
        """Handles on-demand commands dispatched from frontend."""
        return {"success": False, "error": f"Action '{action}' not implemented on {self.name}"}

    def get_state(self):
        with self.lock:
            return {
                "name": self.name,
                "configured": self.configured,
                "status": self.status,
                "missing_keys": self.missing_keys,
                "last_updated": self.last_updated,
                "data": self.data,
                "recent_events": list(self.recent_events)
            }
