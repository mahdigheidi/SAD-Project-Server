import os
import sys
import threading
import requests
from file.hash import hash_md5
from file.segment import Segment
from manager.env import get_partition_count

BROKER_PROJECT_PATH = os.getenv("BROKER_PROJECT_PATH", "/app/")
sys.path.append(os.path.abspath(BROKER_PROJECT_PATH))


class Write:
    _instances = {}
    _write_lock = threading.Lock()

    def __new__(cls, partition: str, replica: str = None):
        if f"{partition}-{replica}" not in cls._instances:
            cls._instances[f"{partition}-{replica}"] = super(Write, cls).__new__(cls)
        return cls._instances[f"{partition}-{replica}"]

    def __init__(self, partition: str, replica: str):
        if hasattr(self, 'initialized'):
            return
        self.initialized = True

        self.partition = partition
        self.segment = Segment(partition, replica)
        self.replica = replica

    def write_data(self, key: str, value: str):
        with self._write_lock:
            md5 = hash_md5(key)
            partition_count = get_partition_count()
            if int(md5, 16) % partition_count != ((int(self.partition) - 1) % partition_count):
                raise Exception(f"key is not for this partition, fuck {md5} {key} {partition_count}")

            appended = self.segment.append(key, value)
            if not appended:
                return False

            replicated = self.send_to_replica(key, value)
            if not replicated:
                return False

            return self.segment.approve_appending()

    def replicate_data(self, key: str, value: bytes):
        if self.segment.append(key, value):
            return self.segment.approve_appending()

    def send_to_replica(self, key: str, value: str) -> bool:
        if self.replica is None:
            print("replica is None, skip it")
            return True

        url = f'{self.replica}/replica/data'
        response = requests.post(
            url,
            json={'key': key, 'value': value, 'partition': self.partition},
            timeout=2,
        )

        if response.status_code != 200:
            print(response, flush=True)
            return False
        return True
