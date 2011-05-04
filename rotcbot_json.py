import RotcWatcher
import json
import time

class RotcJSON(RotcWatcher.Watcher):
	def __init__(self, json_path, timeout=30):
		self.json_path = json_path
		self.timeout = timeout

		RotcWatcher.Watcher.__init__(self)

	def run(self):
		while 1:
			self.iteration()
			time.sleep(self.timeout)

	def iteration(self):
		self.update_server_list()

		self.write_server_list()

	def write_server_list(self):
		fh = open(self.json_path, 'w')
		data = {'time':int(time.time()),
                        'server_info':self.server_info}
		json.dump(data, fh)
		fh.close()

if __name__ == '__main__':
	rotc_json = RotcJSON("/home/rotc/public_html/rotc_servers.json")
	rotc_json.iteration()

