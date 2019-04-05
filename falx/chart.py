import os

class Visualization(object):
	def __init__(self, data, chart):
		self.data = data
		self.chart = chart

class LayeredChart(object):
	def __init__(self, layers, shared_encs):
		self.layers = layers
		self.shared_encs = shared_encs

class GroupChart(object):
	def __init__(self, enc_group, layer):
		self.layer = layer
		self.enc_group = enc_group

class BarChart(object):
	def __init__(self, enc_x, enc_y, enc_x2, enc_y2):
		self.enc_x = enc_x
		self.enc_y = enc_y
		self.enc_x2 = enc_x2
		self.enc_y2 = enc_y2

class StackedChart(object):
	def __init__(self, chart_ty, stack_ty, enc_x, enc_y, enc_x2, enc_y2, enc_color):
		self.chart_ty = chart_ty
		self.enc_x = enc_x
		self.enc_y = enc_y
		self.enc_x2 = enc_x2
		self.enc_y2 = enc_y2
		self.enc_color = enc_color
		self.stack_ty = stack_ty

class LineChart(object):
	def __init__(self, enc_x, enc_y, enc_color=None, enc_size=None):
		self.enc_x = enc_x
		self.enc_y = enc_y
		self.enc_color = enc_color
		self.enc_size = enc_size

	def to_vl_json(self):
		encodings = {}
		return {
			"mark": "line",
			"encoding": build_encs_vl_json([self.enc_x, self.enc_y, self.enc_color, self.enc_size])
		}

class ScatterPlot(object):
	def __init__(self, mark_ty, enc_x, enc_y, enc_color, enc_size, enc_shape):
		self.mark_ty = mark_ty
		self.enc_x = enc_x
		self.enc_y = enc_y
		self.enc_color = enc_color
		self.enc_size = enc_size
		self.enc_shape = enc_shape

class Encoding(object):
	def __init__(self, channel, field, enc_ty, sort_ty=None):
		self.channel = channel
		self.field = field
		self.enc_ty = enc_ty
		self.sort_ty = sort_ty

	def to_vl_json(self):
		res = {"channel": self.channel, "field": self.field, "type": self.enc_ty}
		if self.sort_ty:
			res["sort_ty"] = self.sort_ty
		return res

def build_encs_vl_json(encodings):
	res = {}
	for e in encodings:
		if e is not None:
			res[e.channel] = e.to_vl_json()
	return res
