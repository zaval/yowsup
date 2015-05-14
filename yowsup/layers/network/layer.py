from yowsup.layers import YowLayer, YowLayerEvent
from yowsup.common.http.httpproxy import HttpProxy
from yowsup.socks import *
import asyncore, socket, logging
logger = logging.getLogger(__name__)

class YowNetworkLayer(YowLayer, asyncore.dispatcher_with_send):
	'''
		send:       bytearray -> None
		receive:    bytearray -> bytearray
	'''

	EVENT_STATE_CONNECT         = "org.openwhatsapp.yowsup.event.network.connect"
	EVENT_STATE_DISCONNECT      = "org.openwhatsapp.yowsup.event.network.disconnect"
	EVENT_STATE_CONNECTED       = "org.openwhatsapp.yowsup.event.network.connected"
	EVENT_STATE_DISCONNECTED    = "org.openwhatsapp.yowsup.event.network.disconnected"
	EVENT_SET_PROXY				= "org.openwhatsapp.yowsip.event.network.setproxy"

	PROP_ENDPOINT               = "org.openwhatsapp.yowsup.prop.endpoint"
	PROP_NET_READSIZE           = "org.openwhatsapp.yowsup.prop.net.readSize"

	def __init__(self):
		YowLayer.__init__(self)
		asyncore.dispatcher.__init__(self)
		httpProxy = HttpProxy.getFromEnviron()
		proxyHandler = None
		if httpProxy != None:
			logger.debug("HttpProxy initialize: %s" % httpProxy)
			def onConnect():
				logger.debug("HttpProxy connected")
				self.proxyHandler = None
				self.handle_connect()
			proxyHandler = httpProxy.handler()
			proxyHandler.onConnect = onConnect
		self.proxyHandler = proxyHandler

		self.socksiproxy = socksocket()

	def onEvent(self, ev):
		if ev.getName() == YowNetworkLayer.EVENT_STATE_CONNECT:
			# self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
			self.family_and_type = socket.AF_INET, socket.SOCK_STREAM
			# self.socksiproxy.setblocking(0)
			self.set_socket(self.socksiproxy)
			self.out_buffer = bytearray()
			endpoint = self.getProp(self.__class__.PROP_ENDPOINT)
			if self.proxyHandler != None:
				logger.debug("HttpProxy connect: %s:%d" % endpoint)
				self.proxyHandler.connect(self, endpoint)
			else:
				self.connect(endpoint)
			return True
		elif ev.getName() == YowNetworkLayer.EVENT_STATE_DISCONNECT:
			self.handle_close(ev.getArg("reason") or "Requested")
			return True
		elif ev.getName() == YowNetworkLayer.EVENT_SET_PROXY:
			proxy = ev.getArg("proxy")
			if proxy is None:
				self.socksiproxy = socksocket()
			else:
				proxy_type = ev.getArg("type")
				if proxy_type == "socks5":
					proxy_type = PROXY_TYPE_SOCKS5
				elif proxy_type == "http":
					proxy_type = PROXY_TYPE_HTTP
				else:
					proxy_type = PROXY_TYPE_SOCKS5

				proxy_login = ev.getArg("username")
				proxy_password = ev.getArg("password")
				try:
					proxy_addr, proxy_port = proxy.rsplit(":", 1)
				except:
					proxy_addr = proxy
					proxy_port = None

				self.socksiproxy.setproxy(proxy_type, proxy_addr, int(proxy_port), username=proxy_login, password=proxy_password)
				return True

	def handle_connect(self):
		if self.proxyHandler != None:
			logger.debug("HttpProxy handle connect")
			self.proxyHandler.send(self)
		else:
			self.emitEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECTED))

	def handle_close(self, reason = "Connection Closed"):
		logger.debug("Disconnected, reason: %s" % reason)
		self.emitEvent(YowLayerEvent(self.__class__.EVENT_STATE_DISCONNECTED, reason = reason, detached=True))
		self.close()
		return False

	def handle_error(self):
		raise

	def handle_read(self):
		readSize = self.getProp(self.__class__.PROP_NET_READSIZE, 1024)
		if self.proxyHandler != None:
			data = self.proxyHandler.recv(self, readSize)
			logger.debug("HttpProxy handle read: %s" % data)
		else:
			data = self.recv(readSize)
			self.receive(data)

	def send(self, data):
		self.out_buffer = self.out_buffer + data
		self.initiate_send()

	def receive(self, data):
		self.toUpper(data)

	def __str__(self):
		return "Network Layer"
