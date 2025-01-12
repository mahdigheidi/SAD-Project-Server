import os
import sys
import threading

from file.indexer import Indexer

SEGMENT_SIZE = 100
BROKER_PROJECT_PATH = os.getenv("BROKER_PROJECT_PATH", "/app/")
sys.path.append(os.path.abspath(BROKER_PROJECT_PATH))


class Segment:
    _instances = {}
    _instances_lock = threading.Lock()
    _append_lock = threading.Lock()
    _read_lock = threading.Lock()
    _sync_lock = threading.Lock()

    def __new__(cls, partition: str, replica: str):
        with cls._instances_lock:
            if f"{partition}-{replica}" not in cls._instances:
                cls._instances[f"{partition}-{replica}"] = super(Segment, cls).__new__(cls)
                cls._instances[f"{partition}-{replica}"].partition = partition
                cls._instances[f"{partition}-{replica}"].indexer = Indexer(partition, replica)

            return cls._instances[f"{partition}-{replica}"]

    def append(self, key: str, value: str):
        try:
            with self._append_lock:
                segment_path = self.write_segment_path()
                if self.indexer.get_write() % SEGMENT_SIZE == 0:
                    os.makedirs(segment_path, exist_ok=True)

                data_file_path = os.path.join(segment_path, f'{self.indexer.get_write()}.dat')

                with open(data_file_path, 'w') as entry_file:
                    entry_file.write(f'{key}: {value}')
        except Exception as e:
            print(f"Error appending data to segment: {e}")
            return False
        return True

    def approve_appending(self):
        try:
            with self._append_lock:
                self.indexer.inc_write()
        except Exception as e:
            print(f"Error inc write index: {e}")
            return False
        return True

    def approve_reading(self):
        try:
            with self._read_lock:
                self.indexer.inc_read()
        except Exception as e:
            print(f"Error inc read index: {e}")
            return False
        return True

    def approve_sync(self):
        try:
            with self._sync_lock:
                self.indexer.inc_sync()
        except Exception as e:
            print(f"Error inc sync index: {e}")
            return False
        return True

    def read(self):
        read_index = self.indexer.get_read()
        segment_path = self.read_segment_path()

        data_file_path = os.path.join(segment_path, f'{read_index}.dat')

        if os.path.exists(data_file_path):  # TODO: get lock
            try:
                with open(data_file_path, 'r') as entry_file:
                    data = entry_file.read()

                    key, value = data.split(': ', 1)
                    return key, value
            except Exception as e:
                print(f"Error reading file {data_file_path}: {e}")
                return None, None
        else:
            print(f"File not found: {data_file_path}")
            return None, None

    def write_segment_path(self):
        segment_number = self.write_segment_number()
        return self.__path(segment_number)

    def read_segment_path(self):
        segment_number = self.read_segment_number()
        return self.__path(segment_number)

    def write_segment_number(self):
        write_index = self.indexer.get_write()
        return write_index // SEGMENT_SIZE + 1

    def read_segment_number(self):
        read_index = self.indexer.get_read()
        return read_index // SEGMENT_SIZE + 1

    def __path(self, segment_number: int) -> str:
        current_working_directory = os.getcwd()
        return os.path.join(
            current_working_directory,
            'data',
            'partition_data',
            f'{self.partition}',
            f'segment_{segment_number}'
        )

    def get_read_index(self) -> int:
        return self.indexer.get_read()

    def get_write_index(self) -> int:
        return self.indexer.get_write()

    def get_sync_index(self) -> int:
        return self.indexer.get_sync()
