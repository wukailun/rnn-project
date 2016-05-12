import theano.tensor as T
import numpy
import theano
import sys
sys.path.append('..')
from common.utils import *
from common import mnist_loader
import h5py
from layers.HiddenLayer import HiddenLayer
import theano.tensor.signal.pool as pool
import theano.tensor.nnet.abstract_conv as upsample

# images and labels are the inputs
dataset = mnist_loader.read_data_sets("data")
images, labels = dataset.train.next_batch(batch_size=16)
locs = numpy.random.uniform(low=-1, high=1, size=(images.shape[0], 2))
print images.shape
print labels.shape

# images and locs as inputs


# img : (batch_size, 784)
# normLoc : (batch_size, 2)
img_batch = T.matrix('img')
normLoc = T.matrix('loc')

batch_size = 16
mnist_size = 28
channels = 1
depth = 3
minRadius = 4
sensorBandwidth = 8

hg_size = 128
hl_size = 128
g_size = 256


totalSensorBandwidth = depth * channels * ((2 * sensorBandwidth) ** 2)
""" Sensor
"""
def glimpseSensor(img_batch, normLoc, batch_size=16, mnist_size=28,
                  channels=1, depth=3, minRadius=4, sensorBandwidth=8):
    """ This function calculate the glimpse sensors
        for a batch of images

    :type img_batch: tensor variable with size (batch_size, 784)
    :param img_batch: batch of images

    :type normLoc: tensor variable with size (batch_size, 2)
    :param normLoc: locations of the batch of images

    :return:
    :type zooms: tensor variable with size
                 (batch, depth, channel, height, width)
    :param zooms: zooms of the batch of images
    """
    # from [-1.0, 1.0] -> [0, 28]
    loc = ((normLoc + 1) / 2) * mnist_size
    loc = T.cast(loc, 'int32')

    # img with size (batch, channels, height, width)
    img = T.reshape(img_batch, (batch_size, channels, mnist_size, mnist_size))
    # with size (batch, h, w, 1) after reshape

    zooms = []  # zooms of all the images in batch

    maxRadius = minRadius * (2 ** (depth - 1))  # radius of the largest zoom
    offset = maxRadius

    # zero-padding the batch to (batch, h + 2R, w + 2R, channels)
    img = T.concatenate((T.zeros((batch_size, channels, maxRadius, mnist_size)), img), axis=2)
    img = T.concatenate((img, T.zeros((batch_size, channels, maxRadius, mnist_size))), axis=2)
    img = T.concatenate((T.zeros((batch_size, channels, mnist_size + 2 * maxRadius, maxRadius)), img), axis=3)
    img = T.concatenate((img, T.zeros((batch_size, channels, mnist_size + 2 * maxRadius, maxRadius))), axis=3)
    img = T.cast(img, dtype=theano.config.floatX)

    for k in xrange(batch_size):
        imgZooms = []  # zoom for a single image

        # one_img with size (channels, 2R + size, 2R + size), channels=1 here
        one_img = img[k, :, :, :]

        for i in xrange(depth):
            # r = minR, 2 * minR, ..., (2^(depth - 1)) * minR
            r = minRadius * (2 ** i)

            d_raw = 2 * r  # patch size to be cropped

            loc_k = loc[k, :]  # location of the k-th glimpse, (2, )
            adjusted_loc = T.cast(offset + loc_k - r, 'int32')  # upper-left corner of the patch

            # one_img = T.reshape(one_img, (one_img.shape[0], one_img.shape[1]))

            # Get a zoom patch with size (d_raw, d_raw) from one_image
            # zoom = one_img[adjusted_loc[0]: (adjusted_loc[0] + d_raw),
            #        adjusted_loc[1]: (adjusted_loc[1] + d_raw)]
            zoom = one_img[:, adjusted_loc[0]: (adjusted_loc[0] + d_raw),
                   adjusted_loc[1]: (adjusted_loc[1] + d_raw)]

            if r < sensorBandwidth:  # bilinear-interpolation
                #  here, zoom is a 2D patch with size (2r, 2r)
                # zoom = T.swapaxes(zoom, 1, 2)
                # zoom = T.swapaxes(zoom, 0, 1)  # here, zoom with size (channel, height, width)
                zoom_reshape = T.reshape(zoom, (1, zoom.shape[0], zoom.shape[1], zoom.shape[2]))
                zoom_bandwidth = upsample.bilinear_upsampling(zoom_reshape,
                                                              ratio=(sensorBandwidth / r),
                                                              batch_size=1, num_input_channels=channels)
                # bandwith is with size (channel, height, width)
                zoom_bandwidth = T.reshape(zoom_bandwidth, (zoom_bandwidth.shape[1],
                                                            zoom_bandwidth.shape[2],
                                                            zoom_bandwidth.shape[3]))
            elif r > sensorBandwidth:
                # pooling operation will be down over the last 2 dimension
                # zoom = T.swapaxes(zoom, 1, 2)
                # zoom = T.swapaxes(zoom, 0, 1)  # here, zoom with size (channel, height, width)
                zoom_bandwidth = pool.pool_2d(input=zoom,
                                              ds=(r / sensorBandwidth,
                                                  r / sensorBandwidth),
                                              mode='average_inc_pad',
                                              ignore_border=True)
            else:
                zoom_bandwidth = zoom

            imgZooms.append(zoom_bandwidth)

        zooms.append(T.stack(imgZooms))

    # returned zooms is with size (batch, depth, channel, height, width)
    return T.stack(zooms)




""" Glimpse network
"""


def initial_W_b(rng, n_in, n_out):
    """ This function initializes the
        params for a single layer MLP

    :param n_in: input dimension
    :param n_out: output dimension
    """
    W_values = numpy.asarray(rng.uniform(
        low=-numpy.sqrt(6. / (n_in + n_out)),
        high=numpy.sqrt(6. / (n_in + n_out)),
        size=(n_in, n_out)
    ),
        dtype=theano.config.floatX
    )

    b_values = numpy.zeros((n_out,), dtype=theano.config.floatX)
    return W_values, b_values

""" Initialize parameters
"""
# 1-st set of params: W_hl, b_hl
W_values, b_values = initial_W_b(rng=numpy.random.RandomState(1234),
                                 n_in=2, n_out=hl_size)
W_hl = theano.shared(value=W_values, name='hl_net#W', borrow=True)
b_hl = theano.shared(value=b_values, name='hl_net#b', borrow=True)

# 2-nd set of params: W_hg, b_hg
W_values, b_values = initial_W_b(rng=numpy.random.RandomState(2345),
                                 n_in=totalSensorBandwidth,
                                 n_out=hg_size)
W_hg = theano.shared(value=W_values, name='hg_net#W', borrow=True)
b_hg = theano.shared(value=b_values, name='hg_net#b', borrow=True)


# 3-rd set of params: W_g, b_g
W_values, b_values = initial_W_b(rng=numpy.random.RandomState(3456),
                                 n_in=hl_size + hg_size,
                                 n_out=g_size)
W_g = theano.shared(value=W_values, name='g_net#W', borrow=True)
b_g = theano.shared(value=b_values, name='g_net#b', borrow=True)


# 1-st part, hl_net
hl_output = T.nnet.relu(T.dot(normLoc, W_hl) + b_hl)

# 2-nd part, hg_net
glimpse_input = glimpseSensor(img_batch, normLoc)
hg_input = T.reshape(glimpse_input, (glimpse_input.shape[0],
                                     totalSensorBandwidth))
hg_output = T.nnet.relu(T.dot(hg_input, W_hg) + b_hg)

# 3-rd part, g_net with output size (batch, 256)
g_output = T.nnet.relu(T.dot(T.concatenate((hl_output, hg_output),
                                           axis=1), W_g) + b_g)


"""
# Below is the body of LSTMCell
rng = numpy.random.RandomState(4567)
prefix = 'LSTMCore'
in_size = 256
hid_size = 256

# W and U are the shared variables
W = init_weights(shape=(in_size, 4 * hid_size),
                 name=prefix + '#W')

U = theano.shared(value=numpy.concatenate((ortho_weight(ndim=hid_size),
                                           ortho_weight(ndim=hid_size),
                                           ortho_weight(ndim=hid_size),
                                           ortho_weight(ndim=hid_size)),
                                          axis=1),
                  name=prefix + '#U')

b = init_bias(size=4 * hid_size, name=prefix + '#b')

"""

fn_g = theano.function(inputs=[img_batch, normLoc],
                       outputs=[g_output])
g_out = fn_g(images, locs)[0]
print type(g_out)
print g_out.shape


"""
fn_reshape = theano.function(inputs=[img_batch, normLoc],
                             outputs=[glimpseLayer.zooms])

zoom_reshape = fn_reshape(images, locs)[0]

f = h5py.File('zoom.h5')
f['zoom'] = zoom_reshape
f.close()

print type(zoom_reshape)
print zoom_reshape.shape
"""




