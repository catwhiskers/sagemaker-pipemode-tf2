import argparse
import json
import os

import tensorflow as tf
from sagemaker_tensorflow import PipeModeDataset
from tensorflow.data.experimental import map_and_batch

# from tensorflow.contrib.data import map_and_batch
import logging
logger = logging.getLogger('log')
logging.basicConfig(level=logging.INFO) # Set 

PREFETCH_SIZE = 10
BATCH_SIZE = 64
NUM_PARALLEL_BATCHES = 2
DIMENSION = 1024
EPOCHS = 1


def train_input_fn():
    """Returns input function that would feed the model during training"""
    return _input_fn("train")


def eval_input_fn():
    """Returns input function that would feed the model during evaluation"""
    return _input_fn("eval")


def _input_fn(channel):
    """Returns a Dataset for reading from a SageMaker PipeMode channel."""
    features = {
        "data": tf.io.FixedLenFeature([], tf.string),
        "labels": tf.io.FixedLenFeature([], tf.int64),
    }

    def parse(record):
        parsed = tf.io.parse_single_example(record, features)
        return ({"data": tf.io.decode_raw(parsed["data"], tf.float64)}, parsed["labels"])

    ds = PipeModeDataset(channel)
    if EPOCHS > 1:
        ds = ds.repeat(EPOCHS)
    ds = ds.prefetch(PREFETCH_SIZE)

    ds = ds.apply(
        tf.data.experimental.map_and_batch(parse, batch_size=BATCH_SIZE, num_parallel_batches=NUM_PARALLEL_BATCHES)
    )
    print("dataset:",ds.take(1))
    print("EPOCHS:",EPOCHS)

    return ds

def iterate_fn(channel):
    from os import walk

    f = []
    for (dirpath, dirnames, filenames) in walk("/opt/ml/input/data/"):
        f.extend(filenames)
    print("file descriptors", f)
    manifest = open("/opt/ml/input/data/{}-manifest".format(channel), "r")
    print("manifest file:", manifest.readlines())
    """Returns a Dataset for reading from a SageMaker PipeMode channel."""
    features = {
        "data": tf.io.FixedLenFeature([], tf.string),
        "labels": tf.io.FixedLenFeature([], tf.int64),
    }
    
    def parse(record):
        global data_processed 
        parsed = tf.io.parse_single_example(record, features)
        return ({"data": tf.io.decode_raw(parsed["data"], tf.float64)}, parsed["labels"])

    ds = PipeModeDataset(channel)
    ds = ds.prefetch(PREFETCH_SIZE)
    ds = ds.apply(
        tf.data.experimental.map_and_batch(parse, batch_size=BATCH_SIZE, num_parallel_batches=NUM_PARALLEL_BATCHES)
    )
    
    iterator = iter(ds)
    datalen = 0 
    while datalen < 10: 
        try: 
            opt = iterator.get_next() 
            print(opt)
            datalen+=1 
        except: 
            pass 


def _parse_args():

    parser = argparse.ArgumentParser()

    # Data, model, and output directories
    # model_dir is always passed in from SageMaker. By default this is a S3 path under the default bucket.
    parser.add_argument("--model_dir", type=str)
    parser.add_argument("--sm-model-dir", type=str, default=os.environ.get("SM_MODEL_DIR"))
    parser.add_argument("--hosts", type=list, default=json.loads(os.environ.get("SM_HOSTS")))
    parser.add_argument("--current-host", type=str, default=os.environ.get("SM_CURRENT_HOST"))

    return parser.parse_known_args()


def serving_input_fn():
    inputs = {"data": tf.compat.v1.placeholder(tf.string)}
    return tf.estimator.export.ServingInputReceiver(inputs, inputs)


if __name__ == "__main__":
    args, unknown = _parse_args()
    iterate_fn("visual")
    column = tf.feature_column.numeric_column("data", shape=(DIMENSION,))
    train_spec = tf.estimator.TrainSpec(train_input_fn, max_steps=3000)
    eval_spec = tf.estimator.EvalSpec(eval_input_fn)
    linear_classifier = tf.estimator.LinearClassifier(
        feature_columns=[column], model_dir=args.model_dir
    )
    tf.estimator.train_and_evaluate(linear_classifier, train_spec, eval_spec)

    if args.current_host == args.hosts[0]:
        linear_classifier.export_saved_model(args.sm_model_dir, serving_input_fn)
