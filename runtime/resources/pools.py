"""
Thread Pool Resources (Phase S)
"""
import threading

class ThreadPoolResources:
    @staticmethod
    def create_thread(target, args, name, daemon=True):
        return threading.Thread(target=target, args=args, daemon=daemon, name=name)
