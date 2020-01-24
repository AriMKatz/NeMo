import os

import torch
# noinspection PyPep8Naming
from torch import nn

from nemo.backends.pytorch.nm import TrainableNM
from nemo.core.neural_types import *
from nemo_nlp.transformer.utils import transformer_weights_init

activations = {
    "tanh": nn.Tanh,
    "relu": nn.ReLU,
}

class Encoder(TrainableNM):
    """
    Neural module which consists of MLP followed by softmax classifier for each
    sequence in the batch.

    Args:
        hidden_size (int): hidden size (d_model) of the Transformer
        num_classes (int): number of classes in softmax classifier, e.g. number
            of different sentiments
        num_layers (int): number of layers in classifier MLP
        activation (str): activation function applied in classifier MLP layers
        log_softmax (bool): whether to apply log_softmax to MLP output
        dropout (float): dropout ratio applied to MLP
    """

    @property
    def input_ports(self):
        """Returns definitions of module input ports.

        hidden_states:
            0: AxisType(BatchTag)

            1: AxisType(TimeTag)

            2: AxisType(ChannelTag)
        """
        return {
            "hidden_states": NeuralType({
                0: AxisType(BatchTag),
                1: AxisType(TimeTag),
                2: AxisType(ChannelTag)
            })
        }

    @property
    def output_ports(self):
        """Returns definitions of module output ports.

        logits:
            0: AxisType(BatchTag)

            1: AxisType(ChannelTag)
        """
        return {
            "logits": NeuralType({
                0: AxisType(BatchTag),
                1: AxisType(ChannelTag)
            })
        }

    def __init__(self,
                 hidden_size,
                 activation='tanh',
                 dropout=0.0,
                 use_transformer_pretrained=True):
        super().__init__()
        self.fc = nn.Linear(hidden_size, hidden_size).to(self._device)
        self.activation = getattr(torch, activation)
        self.dropout = nn.Dropout(dropout)

        if use_transformer_pretrained:
            self.apply(
                lambda module: transformer_weights_init(module, xavier=False))
        # self.to(self._device) # sometimes this is necessary

    def forward(self, hidden_states):
        first_token_hidden_states = hidden_states[:, 0]
        logits = self.fc(first_token_hidden_states)
        logits = self.activation(logits)
        logits = self.dropout(logits)
        
        return logits