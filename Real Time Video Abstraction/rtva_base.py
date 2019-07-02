import cv2
import numpy as np
import subprocess as sp
from streamlink import streams as get_streams
from threading import Thread
from queue import Queue
from time import time


class Video:

	def __init__(self, name='FBI camera', delay=1, frame_rate=30):
		self.name = name
		self.delay = delay
		self.frame_rate = frame_rate
		self.asd = 0

	def mouse_event_handler(self, event, x, y, flags, param):
		pass

	def start_plugins(self, plugins):
		for plugin in plugins:
			plugin.start(self)

	def start_additional(self):
		pass

	def run_plugins(self, frame):
		for plugin in self.plugins:
			frame = plugin.run(self, frame)
		return frame

	def pre_processing(self, frame):
		return frame

	def post_processing(self, frame):
		pass

	def key_funcs(self, key):
		if self.plugins:
			for plugin in self.plugins:
				if 'key_func' in dir(plugin): plugin.key_func(key)
		return True

	def stop(self):
		self.video.release()
		for plugin in self.plugins:
			plugin.stop()
		cv2.destroyAllWindows()

	def next_frame(self):
		t = time()
		if t - self.last_frame_time >= self.period:
			self.last_frame_time = t
			return True
		return False

	def run(self):
		while cv2.getWindowProperty(self.name, 0) != -1:
			if not self.next_frame(): continue
			ret, frame = self.video.read()
			if not ret: break

			if self.plugins: frame = self.run_plugins(frame)
			frame = self.pre_processing(frame)
			cv2.imshow(self.name, frame)
			self.post_processing(frame)

			k = cv2.waitKey(self.delay)
			if not self.key_funcs(k):
				break

		self.stop()

	def start(self, capture=0, plugins=None):
		self.video = cv2.VideoCapture(capture)
		cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)

		if plugins: self.start_plugins(plugins)
		self.plugins = plugins
		self.start_additional()

		cv2.setMouseCallback(self.name, self.mouse_event_handler)
		self.period = 1/self.frame_rate
		self.last_frame_time = time()

		self.run()


class Stream(Video):

	def stop(self):
		for plugin in self.plugins:
			plugin.stop()
		cv2.destroyAllWindows()

	def get_frames(self):
		while cv2.getWindowProperty(self.name, 0) != -1:
			raw = self.pipe.stdout.read(self.height * self.width * 3)
			image = np.frombuffer(raw, np.uint8).reshape((self.height, self.width, 3))
			self.buffer.put(image)

	def run(self):
		while cv2.getWindowProperty(self.name, 0) != -1:
			if not self.next_frame(): continue
			if self.buffer.qsize():
				frame = self.buffer.get()
			else:
				continue

			if self.plugins: frame = self.run_plugins(frame)
			frame = self.pre_processing(frame)
			cv2.imshow(self.name, frame)
			self.post_processing(frame)

			k = cv2.waitKey(self.delay)
			if not self.key_funcs(k):
				break

		self.stop()

	def start(self, url, resolution='480p', plugins=None):
		res_dict = {'360p': {'width':640, 'height':360},
					'480p': {'width':854, 'height':480},
					'720p': {'width':1280, 'height':720},
					'720p60':{'width':1280, 'height':720},
					'1080p':{'width':1920, 'height':1080},
					'1080p60':{'width':1920, 'height':1080}}

		streams = get_streams(url)
		if resolution not in streams.keys():
			print('Selected resolution not available.')
			return None
		feed = streams[resolution].url
		if 'twitch' in url: res_dict['480p'] = {'width':852, 'height':480}
		if resolution[-2:] == '60': self.frame_rate = 60
		self.height = res_dict[resolution]['height']
		self.width = res_dict[resolution]['width']

		spcmd = ['ffmpeg',
				 '-i', feed,
				 '-loglevel', 'quiet',
				 '-an',
				 '-f', 'image2pipe',
				 '-pix_fmt', 'bgr24',
				 '-vcodec', 'rawvideo',
				 '-']
		self.pipe = sp.Popen(spcmd, stdin=sp.PIPE, stdout=sp.PIPE)
		self.buffer = Queue()

		cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
		cv2.setMouseCallback(self.name, self.mouse_event_handler)
		self.period = 1/self.frame_rate
		self.last_frame_time = time()

		if plugins: self.start_plugins(plugins)
		self.plugins = plugins
		self.start_additional()

		buffer_thread = Thread(target=self.get_frames)
		buffer_thread.start()
		self.run()