import tensorflow as tf
import numpy as np
from tensorflow.python.framework import ops
from tensorflow.python.framework import tensor_shape
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import gen_nn_ops


def conv1d_transpose(
    value,
    filter,  # pylint: disable=redefined-builtin
    output_shape,
    stride,
    padding="SAME",
    data_format="NWC",
    name=None):
  """The transpose of `conv1d`.
  This operation is sometimes called "deconvolution" after [Deconvolutional
  Networks](http://www.matthewzeiler.com/pubs/cvpr2010/cvpr2010.pdf), but is
  actually the transpose (gradient) of `conv1d` rather than an actual
  deconvolution.
  Args:
    value: A 3-D `Tensor` of type `float` and shape
      `[batch, in_width, in_channels]` for `NWC` data format or
      `[batch, in_channels, in_width]` for `NCW` data format.
    filter: A 3-D `Tensor` with the same type as `value` and shape
      `[filter_width, output_channels, in_channels]`.  `filter`'s
      `in_channels` dimension must match that of `value`.
    output_shape: A 1-D `Tensor` representing the output shape of the
      deconvolution op.
    stride: An `integer`.  The number of entries by which
      the filter is moved right at each step.
    padding: A string, either `'VALID'` or `'SAME'`. The padding algorithm.
      See the @{tf.nn.convolution$comment here}
    data_format: A string. 'NHWC' and 'NCHW' are supported.
    name: Optional name for the returned tensor.
  Returns:
    A `Tensor` with the same type as `value`.
  Raises:
    ValueError: If input/output depth does not match `filter`'s shape, or if
      padding is other than `'VALID'` or `'SAME'`.
  """
  with ops.name_scope(name, "conv1d_transpose",
                      [value, filter, output_shape]) as name:
    output_shape_ = ops.convert_to_tensor(output_shape, name="output_shape")
    if not output_shape_.get_shape().is_compatible_with(tensor_shape.vector(3)):
      raise ValueError("output_shape must have shape (3,), got {}".format(
          output_shape_.get_shape()))

    # The format could be either NWC or NCW, map to NHWC or NCHW
    if data_format is None or data_format == "NWC":
      data_format_2d = "NHWC"
      axis = 2
    elif data_format == "NCW":
      data_format_2d = "NCHW"
      axis = 1
    else:
      raise ValueError("data_format must be \"NWC\" or \"NCW\".")

    if not value.get_shape()[axis].is_compatible_with(filter.get_shape()[2]):
      raise ValueError("input channels does not match filter's input channels, "
                       "{} != {}".format(value.get_shape()[axis],
                                         filter.get_shape()[2]))

    if isinstance(output_shape, (list, np.ndarray)):
      # output_shape's shape should be == [3] if reached this point.
      if not filter.get_shape()[1].is_compatible_with(output_shape[axis]):
        raise ValueError(
            "output_shape does not match filter's output channels, "
            "{} != {}".format(output_shape[axis],
                              filter.get_shape()[1]))

    if padding != "VALID" and padding != "SAME":
      raise ValueError("padding must be either VALID or SAME:"
                       " {}".format(padding))

    # Reshape the input tensor to [batch, 1, in_width, in_channels]
    if data_format_2d == "NHWC":
      output_shape_ = array_ops.concat(
          [output_shape_[:1], [1], output_shape_[1:]], axis=0)
      spatial_start_dim = 1
      strides = [1, 1, stride, 1]
    else:
      output_shape_ = array_ops.concat(
          [output_shape_[:2], [1], output_shape_[2:]], axis=0)
      spatial_start_dim = 2
      strides = [1, 1, 1, stride]
    value = array_ops.expand_dims(value, spatial_start_dim)
    filter = array_ops.expand_dims(filter, 0)  # pylint: disable=redefined-builtin

    result = gen_nn_ops.conv2d_backprop_input(
        input_sizes=output_shape_,
        filter=filter,
        out_backprop=value,
        strides=strides,
        padding=padding,
        data_format=data_format_2d,
        name=name)
    return array_ops.squeeze(result, [spatial_start_dim])


def linear(input_, output_size, scope=None, stddev=0.02, bias_start=0.0, with_w=False):
    shape = input_.get_shape().as_list()
    with tf.variable_scope(scope or 'Linear'):
        matrix = tf.get_variable('Matrix', [shape[1], output_size], tf.float32,
                                 tf.random_normal_initializer(stddev=stddev))
        bias = tf.get_variable('bias', [output_size],
            initializer=tf.constant_initializer(bias_start))
        if with_w:
            return tf.matmul(input_, matrix) + bias, matrix, bias
        else:
            return tf.matmul(input_, matrix) + bias


def my_model_fn(features, batch_size, fc_filters, tconv_dims, tconv_filters):
    """
    My customized model function
    :param features: input features
    :param output_size: dimension of output data
    :return:
    """
    fc = features
    for cnt, filters in enumerate(fc_filters):
        fc = tf.layers.dense(inputs=fc, units=filters, activation=tf.nn.leaky_relu, name='fc{}'.format(cnt),
                             kernel_initializer=tf.random_normal_initializer(stddev=0.02))
    up = tf.expand_dims(fc, axis=2)
    feature_dim = fc_filters[-1]

    last_filter = 1
    for cnt, (up_size, up_filter) in enumerate(zip(tconv_dims, tconv_filters)):
        assert up_size%feature_dim == 0
        stride = up_size // feature_dim
        feature_dim = up_size
        f = tf.Variable(tf.random_normal([3, up_filter, last_filter]))
        up = conv1d_transpose(up, f, [batch_size, up_size, up_filter], stride, name='up{}'.format(cnt))
        last_filter = up_filter

    up = tf.layers.conv1d(up, 1, 1, activation=None, name='conv_final')

    return tf.squeeze(up, axis=2)


def my_model_fn_linear(features, batch_size, fc_filters, tconv_dims, tconv_filters):
    """
    My customized model function
    :param features: input features
    :param output_size: dimension of output data
    :return:
    """
    fc = features
    for cnt, filters in enumerate(fc_filters):
        fc = linear(fc, filters, 'fc_linear_{}'.format(cnt), with_w=False)
        fc = tf.nn.leaky_relu(fc)

    up = tf.expand_dims(fc, axis=2)
    feature_dim = fc_filters[-1]

    last_filter = 1
    for cnt, (up_size, up_filter) in enumerate(zip(tconv_dims, tconv_filters)):
        assert up_size%feature_dim == 0
        stride = up_size // feature_dim
        feature_dim = up_size
        f = tf.Variable(tf.random_normal([3, up_filter, last_filter]))
        up = conv1d_transpose(up, f, [batch_size, up_size, up_filter], stride, name='up{}'.format(cnt))
        last_filter = up_filter

    up = tf.layers.conv1d(up, 1, 1, activation=None, name='conv_final')

    return tf.squeeze(up, axis=2)


def my_model_fn_linear_conv1d(features, batch_size, fc_filters, tconv_dims, tconv_filters):
    """
    My customized model function
    :param features: input features
    :param output_size: dimension of output data
    :return:
    """
    fc = features
    for cnt, filters in enumerate(fc_filters):
        fc = linear(fc, filters, 'fc_linear_{}'.format(cnt), with_w=False)
        fc = tf.nn.leaky_relu(fc)

    up = tf.expand_dims(fc, axis=2)
    feature_dim = fc_filters[-1]

    last_filter = 1
    for cnt, (up_size, up_filter) in enumerate(zip(tconv_dims, tconv_filters)):
        assert up_size%feature_dim == 0
        stride = up_size // feature_dim
        feature_dim = up_size
        f = tf.Variable(tf.random_normal([3, up_filter, last_filter]))
        up = conv1d_transpose(up, f, [batch_size, up_size, up_filter], stride, name='up{}'.format(cnt))
        up = tf.layers.conv1d(up, up_filter, 3, activation=tf.nn.leaky_relu, name='conv_up{}'.format(cnt),
                              padding='same')
        last_filter = up_filter

    up = tf.layers.conv1d(up, 1, 1, activation=None, name='conv_final')

    return tf.squeeze(up, axis=2)
