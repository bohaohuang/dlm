import os
import csv
import argparse
import numpy as np
import matplotlib.pyplot as plt
import utils
import data_reader
import network_maker
import network_helper


INPUT_SIZE = 2
X_RANGE = [0, 1]
Y_RANGE = [i for i in range(2, 1003)]
CROSS_VAL = 5
VAL_FOLD = 0
BATCH_SIZE = 20
SHUFFLE_SIZE = 5
VERB_STEP = 25
EVAL_STEP = 250
TRAIN_STEP = 1500
LEARN_RATE = 1e-3
DECAY_STEP = 10000
DECAY_RATE = 0.96
TRAIN_FILE = 'TrainDataV9.txt'
VALID_FILE = 'TestDataV9.txt'
FORCE_RUN =True
MODEL_NAME = '20180705_125935'


def read_flag():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-size', type=int, default=INPUT_SIZE, help='input size')
    parser.add_argument('--x-range', type=list, default=X_RANGE, help='columns of input parameters')
    parser.add_argument('--y-range', type=list, default=Y_RANGE, help='columns of output parameters')
    parser.add_argument('--cross-val', type=int, default=CROSS_VAL, help='# cross validation folds')
    parser.add_argument('--val-fold', type=int, default=VAL_FOLD, help='fold to be used for validation')
    parser.add_argument('--batch-size', default=BATCH_SIZE, type=int, help='batch size (100)')
    parser.add_argument('--shuffle-size', default=SHUFFLE_SIZE, type=int, help='shuffle size (100)')
    parser.add_argument('--verb-step', default=VERB_STEP, type=int, help='# steps between every print message')
    parser.add_argument('--eval-step', default=EVAL_STEP, type=int, help='# steps between evaluations')
    parser.add_argument('--train-step', default=TRAIN_STEP, type=int, help='# steps to train on the dataset')
    parser.add_argument('--learn-rate', default=LEARN_RATE, type=float, help='learning rate')
    parser.add_argument('--decay-step', default=DECAY_STEP, type=int,
                        help='decay learning rate at this number of steps')
    parser.add_argument('--decay-rate', default=DECAY_RATE, type=float,
                        help='decay learn rate by multiplying this factor')
    parser.add_argument('--force-run', default=FORCE_RUN, type=bool, help='force it to rerun')
    parser.add_argument('--model-name', default=MODEL_NAME, type=str, help='name of the model')
    parser.add_argument('--train-file', default=TRAIN_FILE, type=str, help='name of the training file')
    parser.add_argument('--valid-file', default=VALID_FILE, type=str, help='name of the validation file')

    flags = parser.parse_args()
    return flags


def compare_truth_pred(pred_file, truth_file):
    """
    Read truth and pred from csv files, compute their mean-absolute-error and the mean-squared-error
    :param pred_file: full path to pred file
    :param truth_file: full path to truth file
    :return: mae and mse
    """
    pred = np.loadtxt(pred_file, delimiter=' ')
    truth = np.loadtxt(truth_file, delimiter=' ')

    mae = np.mean(np.abs(pred-truth), axis=1)
    mse = np.mean(np.square(pred-truth), axis=1)

    return mae, mse


def main(flags):
    ckpt_dir = os.path.join(os.path.dirname(__file__), 'models', flags.model_name)
    fc_filters, tconv_dims, tconv_filters = network_helper.get_parameters(ckpt_dir)

    # initialize data reader
    if len(tconv_dims) == 0:
        output_size = fc_filters[-1]
    else:
        output_size = tconv_dims[-1]
    reader = data_reader.DataReader(input_size=flags.input_size, output_size=output_size,
                                    x_range=flags.x_range, y_range=flags.y_range, cross_val=flags.cross_val,
                                    val_fold=flags.val_fold, batch_size=flags.batch_size,
                                    shuffle_size=flags.shuffle_size)
    features, labels, train_init_op, valid_init_op = reader.get_data_holder_and_init_op(
        (flags.train_file, flags.valid_file)
    )

    # make network
    ntwk = network_maker.CnnNetwork(features, labels, utils.my_model_fn, flags.batch_size,
                                    fc_filters=fc_filters, tconv_dims=tconv_dims,
                                    tconv_filters=tconv_filters, learn_rate=flags.learn_rate,
                                    decay_step=flags.decay_step, decay_rate=flags.decay_rate, make_folder=False)

    # evaluate the results if the results does not exist or user force to re-run evaluation
    save_file = os.path.join(os.path.dirname(__file__), 'data', 'test_pred_{}.csv'.format(flags.model_name))
    if FORCE_RUN or (not os.path.exists(save_file)):
        print('Evaluating the model ...')
        pred_file, truth_file = ntwk.evaluate(valid_init_op, ckpt_dir=ckpt_dir, model_name=flags.model_name)
    else:
        pred_file = save_file
        truth_file = os.path.join(os.path.dirname(__file__), 'data', 'test_truth.csv')

    mae, mse = compare_truth_pred(pred_file, truth_file)

    plt.figure(figsize=(12, 6))
    plt.hist(mse, bins=100)
    plt.xlabel('Mean Squared Error')
    plt.ylabel('cnt')
    plt.suptitle('FC + TCONV (Avg MSE={:.4e}'.format(np.mean(mse)))
    plt.savefig(os.path.join(os.path.dirname(__file__), 'data',
                             'fc_tconv_single_channel_result_cmp_{}.png'.format(flags.model_name)))
    plt.show()


if __name__ == '__main__':
    flags = read_flag()
    main(flags)
