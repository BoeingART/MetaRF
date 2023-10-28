import csv
import numpy as np
import pandas as pd
import kennard_stone as ks
import tensorflow as tf
import tensorflow.keras as keras
import tensorflow.keras.backend as keras_backend
from sklearn import metrics
from pandas.core.frame import DataFrame
import sys
import time
import numpy as np

from pathlib import Path as path

BASE_DIR = path(__file__).parent / path("..") # The current working directory
input_path = path(BASE_DIR, 'data/ullmann-ma_reaction.csv') # Relative path
model_path = path(BASE_DIR, 'model/model_trained.h5')

data_all = pd.read_csv(input_path) # Read the csv file with relative path

list_train = [1,2,3,4]
list_val = [5]
list_test = [6,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]

dft_num = 120 # Number of the original reaction encoding

class Model(keras.Model):
    def __init__(self):
        super().__init__()
        self.hidden1 = keras.layers.Dense(40, input_shape=(feature_num,))
        self.hidden2 = keras.layers.Dense(40)
        self.out = keras.layers.Dense(1)
        
    def forward(self, x):
        x = keras.activations.relu(self.hidden1(x))
        x = keras.activations.relu(self.hidden2(x))
        x = self.out(x)
        return x

    def call(self, x):
        x = keras.activations.relu(self.hidden1(x))
        x = keras.activations.relu(self.hidden2(x))
        x = self.out(x)
        return x

def loss_function(pred_y, y):
  return keras_backend.mean(keras.losses.mean_squared_error(y, pred_y))

def np_to_tensor(list_of_numpy_objs):
    return (tf.convert_to_tensor(obj) for obj in list_of_numpy_objs)
    

def compute_loss(model, x, y, loss_fn=loss_function):
    logits = model.forward(x)
    mse = loss_fn(y, logits)
    return mse, logits


def compute_gradients(model, x, y, loss_fn=loss_function):
    with tf.GradientTape() as tape:
        loss, _ = compute_loss(model, x, y, loss_fn)
    return tape.gradient(loss, model.trainable_variables), loss


def apply_gradients(optimizer, gradients, variables):
    optimizer.apply_gradients(zip(gradients, variables))


def train_batch(x, y, model, optimizer):
    tensor_x, tensor_y = np_to_tensor((x, y))
    gradients, loss = compute_gradients(model, tensor_x, tensor_y)
    apply_gradients(optimizer, gradients, model.trainable_variables)
    return loss


def copy_model(model, x):

    copied_model = Model()
    copied_model.forward(tf.convert_to_tensor(x))
    
    copied_model.set_weights(model.get_weights())
    return copied_model  

def eval_all_ks_tune_num(model,tune_num=10):

  y_test_all = []
  y_pred_all = []

  for i in range(len(list_test)):
    y_test,y_pred,df1,df2,df_plot = eval_ks_tune_num(model,number = list_test[i],tune_num=tune_num)

    y_test_all += y_test
    y_pred_all += y_pred
  
  print(y_test_all)
  print(y_pred_all)
  
  r2 = metrics.r2_score(y_test_all, y_pred_all)
  rmse = np.sqrt(metrics.mean_squared_error(y_test_all, y_pred_all))

  return r2,rmse

def eval_ks_tune_num(model, data = data_all, num_steps=(0, 1, 2,3,4,5,6,7,8,9,10), lr=0.00001, number = 16,tune_num=10):

    df1 = pd.DataFrame()
    df2 = pd.DataFrame()
    df_plot = pd.DataFrame()
    tmp = data_all_copy

    data_used = tmp.reset_index().drop(columns=['index'])
    data_used_plot = tmp.reset_index()

    X = data_used.iloc[:,feature_num+2:feature_num+4]
    y = data_used.iloc[:,feature_num+1:feature_num+2]

    all_num = len(data_used)

    X_train_, X_test_, y_train_, y_test_ = ks.train_test_split(X, y, test_size = 1 - tune_num/all_num)
    top_k_idx = X_train_.index.tolist()

    data_sampled = data_used.loc[top_k_idx]
    data_sampled_plot = data_used_plot.loc[top_k_idx].set_index(["index"])

    # batch used for training
    data_minus = pd.concat([data_used, data_sampled]).drop_duplicates(keep=False) # TODO: change with pd.concat

    x_test = data_minus.iloc[:,0:feature_num].values
    y_test = data_minus[['yield']].values.flatten().tolist()
    
    x = data_sampled.iloc[:,0:feature_num].values
    y = data_sampled[['yield']].values

    # copy model so we can use the same model multiple times
    copied_model = copy_model(model, x)
    
    # use SGD for this part of training as described in the paper
    optimizer = keras.optimizers.SGD(learning_rate=lr)
    
    # run training and log fit results
    fit_res,best_res = evaluation(copied_model, optimizer, x, y, x_test, y_test, num_steps)
    
    #y_pred = np.clip(best_res[0][1].numpy().flatten(), 0, 100)
    #y_pred = best_res[0][1].numpy().flatten()
    y_pred = fit_res[1][1].numpy().flatten().tolist()

    
    df1 = data_sampled
    df2 = data_minus
    df_plot = data_sampled_plot

    return y_test,y_pred,df1,df2,df_plot

def evaluation(model, optimizer, x, y, x_test, y_test, num_steps=(0, 1, 2,3,4,5,6,7,8,9,10)):

    fit_res = []
    best_res = []
    min_loss = 1000000000
    
    tensor_x_test, tensor_y_test = np_to_tensor((x_test, y_test))
    
    # If 0 in fits we log the loss before any training
    if 0 in num_steps:
        loss, logits = compute_loss(model, tensor_x_test, tensor_y_test)
        fit_res.append((0, logits, loss))
        
    for step in range(1, np.max(num_steps) + 1):
        train_batch(x, y, model, optimizer)
        loss, logits = compute_loss(model, tensor_x_test, tensor_y_test)
        if step in num_steps:
            fit_res.append(
                (
                    step, 
                    logits,
                    loss
                )
            )

        if loss < min_loss:
          best_res = []
          best_res.append(
                (
                    step, 
                    logits,
                    loss
                )
            )
          min_loss = loss
    
    return fit_res,best_res   

feature_num = 320
data_all_copy = data_all.copy(deep=True)

maml_saved = Model()
maml_saved.build(input_shape = (320,320))
maml_saved.load_weights(model_path)

print(eval_all_ks_tune_num(maml_saved,tune_num=5))

