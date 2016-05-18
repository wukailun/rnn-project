import theano
import theano.tensor as T
import numpy
from head import *
from controller_feedforward import *
from controller_lstm import *
from common.utils import *
import scipy
import operator

""" Test the controller

batch_size = 5
input_size = 8
output_size = 8
mem_size = 128
mem_width = 20
layer_sizes = [100, 150]
num_heads = 3

model = ControllerLSTM(layer_sizes=layer_sizes)

x_t = T.matrix('x_t')
read_tm1_list = [T.matrix('read_tm1_%d' % h) for h in xrange(num_heads)]
c_tm1_list = [T.matrix('c_tm1_%d' % l) for l in xrange(len(layer_sizes))]
h_tm1_list = [T.matrix('h_tm1_%d' % l) for l in xrange(len(layer_sizes))]

inputs = [x_t]
inputs.extend(read_tm1_list)
inputs.extend(c_tm1_list)
inputs.extend(h_tm1_list)

c_t_list, h_t_list = model.step(x_t, read_tm1_list, c_tm1_list, h_tm1_list)

outputs = []
outputs.extend(c_t_list)
outputs.extend(h_t_list)

fn_lstm = theano.function(inputs=inputs,
                          outputs=outputs)

data_x = numpy.random.randn(batch_size, input_size).astype(dtype=theano.config.floatX)
read_list = [numpy.random.randn(batch_size, mem_width).astype(dtype=theano.config.floatX) for h in range(num_heads)]
c_list = [numpy.random.randn(batch_size, layer_sizes[l]).astype(dtype=theano.config.floatX) for l in range(len(layer_sizes))]
h_list = [numpy.random.randn(batch_size, layer_sizes[l]).astype(dtype=theano.config.floatX) for l in range(len(layer_sizes))]

data_in = [data_x] + read_list + c_list + h_list


data_out = fn_lstm(data_in[0], data_in[1], data_in[2], data_in[3], data_in[4], data_in[5], data_in[6], data_in[7])  # error occurs here, we should break list data_in

print type(data_out)
print len(data_out)

print type(data_out[0])
print data_out[0].shape

print type(data_out[1])
print data_out[1].shape

print type(data_out[2])
print data_out[2].shape

print type(data_out[3])
print data_out[3].shape
"""


batch_size = 5
number = 0
last_dim = 100
mem_size = 128
mem_width = 20
shift_width = 3
similarity = cosine_sim
is_write = False


model = Head(is_write=is_write)

M_tm1 = T.matrix('M_tm1')  # with size (mem_size, mem_width)
w_tm1 = T.matrix('w_tm1')  # with size (batch_size, mem_size)
last_hidden = T.matrix('last_hidden')  # with size (batch, last_dim)

w_t, read_t = model.step(M_tm1=M_tm1, w_tm1=w_tm1,
                                 last_hidden=last_hidden)

fn_head = theano.function(inputs=[M_tm1, w_tm1, last_hidden],
                          outputs=[w_t, read_t])

M_in = numpy.random.randn(mem_size, mem_width)
w_in = numpy.random.randn(batch_size, mem_size)
last_in = numpy.random.randn(batch_size, last_dim)

w_out, read_out = fn_head(M_in, w_in, last_in)

print type(w_out)
print w_out.shape

print type(read_out)
print read_out.shape
