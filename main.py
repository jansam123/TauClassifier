"""
Main Code Body
"""
from variables import variables_dictionary
from models import tauid_rnn_model
from DataGenerator import DataGenerator
from files import files_dictionary
import time
from utils import logger

if __name__ == "__main__":

      # Start timer
      start_time = time.time()

      logger.log("Beginning dataset preparation", 'INFO')

      # Initialize Generators
      training_batch_generator = DataGenerator(files_dictionary, variables_dictionary, 100000, cuts="TauJets.truthProng == 1")
      #testing_batch_generator = DataGenerator(X_test_idx, variables_dictionary)
      #validation_batch_generator = DataGenerator(X_val_idx, variables_dictionary)

      # Initialize Model
      shape_trk, shape_conv_trk, shape_shot_pfo, shape_neut_pfo, shape_jet, _, _ = training_batch_generator.get_batch_shapes()

      print(f"Track shape = {shape_trk}   Conv Track shape = {shape_conv_trk}  Shot PFO shape = {shape_shot_pfo} "
            f"Neutral PFO shape = {shape_neut_pfo}  Jet shape = {shape_jet}")

      model = tauid_rnn_model(shape_trk[1:], shape_cls[1:], shape_jet[1:])
      model.summary()
      model.compile(optimizer="adam", loss="binary_crossentropy",  metrics=["accuracy"])

      # Train Model
      history = model.fit(training_batch_generator, epochs=100, max_queue_size=4, use_multiprocessing=False, shuffle=True)

