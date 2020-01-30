"""
Copyright 2018 The Google AI Language Team Authors and
The HuggingFace Inc. team.
Copyright (c) 2019, NVIDIA CORPORATION.  All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Utility functions for GLUE tasks
Some transformer of this code were adapted from the HuggingFace library at
https://github.com/huggingface/transformers
"""

import numpy as np
from torch.utils.data import Dataset

import nemo

__all__ = ['GLUEDataset']

class GLUEDataset(Dataset):
    def __init__(self, data_dir, tokenizer, max_seq_length, processor, output_mode, evaluate, token_params):
        self.tokenizer = tokenizer
        self.label_list = processor.get_labels()
        self.examples = processor.get_dev_examples(data_dir) if evaluate else processor.get_train_examples(data_dir)
        self.features = convert_examples_to_features(
            self.examples, self.label_list, max_seq_length, tokenizer, output_mode, **token_params
        )

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        feature = self.features[idx]
        return (
            np.array(feature.input_ids),
            np.array(feature.segment_ids),
            np.array(feature.input_mask, dtype=np.long),
            np.array(feature.label_id),
        )


def convert_examples_to_features(
    examples,
    label_list,
    max_seq_length,
    tokenizer,
    output_mode,
    bos_token=None,
    eos_token='[SEP]',
    pad_token='[PAD]',
    cls_token='[CLS]',
    sep_token_extra=None,
    cls_token_at_end=False,
    cls_token_segment_id=0,
    pad_token_segment_id=0,
    pad_on_left=False,
    mask_padding_with_zero=True,
    sequence_a_segment_id=0,
    sequence_b_segment_id=1,
):
    """ Loads a data file into a list of `InputBatch`s
        `cls_token_at_end` define the location of the CLS token:
            - False (Default, BERT/XLM pattern): [CLS] + A + [SEP] + B + [SEP]
            - True (XLNet/GPT pattern): A + [SEP] + B + [SEP] + [CLS]
        `cls_token_segment_id` define the segment id associated to the CLS
        token (0 for BERT, 2 for XLNet)
         The convention in BERT is:
         (a) For sequence pairs:
          tokens:   [CLS] is this jack ##ville ? [SEP] no it is not . [SEP]
          type_ids:   0   0  0    0    0       0   0   1  1  1  1   1   1
         (b) For single sequences:
          tokens:   [CLS] the dog is hairy . [SEP]
          type_ids:   0   0   0   0  0     0   0
         Where "type_ids" are used to indicate whether this is the first
         sequence or the second sequence. The embedding vectors for `type=0`
         and `type=1` were learned during pre-training and are added to the
         wordpiece embedding vector (and position vector). This is
         not *strictly* necessarysince the [SEP] token unambiguously separates
         the sequences, but it makes it easier for the model to learn
         the concept of sequences.
         For classification tasks, the first vector (corresponding to [CLS])
         is used as as the "sentence vector". Note that this only makes sense
         because the entire model is fine-tuned.
         For NMT:
         (a) For sequence pairs:
          tokens:<BOS> is this jack ##ville ? <EOS> <BOS> no it is not . <EOS>
          type_ids:0   0  0    0    0       0   0     1   1  1  1  1   1   1
         (b) For single sequences:
          tokens:   <BOS> the dog is hairy . <EOS>
          type_ids:   0   0   0   0  0     0   0
    """
    label_map = {label: i for i, label in enumerate(label_list)}

    features = []
    for ex_index, example in enumerate(examples):
        if ex_index % 10000 == 0:
            nemo.logging.info("Writing example %d of %d" % (ex_index, len(examples)))

        tokens_a = tokenizer.text_to_tokens(example.text_a)

        tokens_b = None
        if example.text_b:
            tokens_b = tokenizer.text_to_tokens(example.text_b)

            special_tokens_count = 2 if eos_token else 0
            special_tokens_count += 1 if sep_token_extra else 0
            special_tokens_count += 2 if bos_token else 0
            special_tokens_count += 1 if cls_token else 0
            _truncate_seq_pair(tokens_a, tokens_b, max_seq_length - special_tokens_count)
        else:
            special_tokens_count = 1 if eos_token else 0
            special_tokens_count += 1 if sep_token_extra else 0
            special_tokens_count += 1 if bos_token else 0
            if len(tokens_a) > max_seq_length - special_tokens_count:
                tokens_a = tokens_a[: max_seq_length - special_tokens_count]
        # Add special tokens to sequence_a
        tokens = tokens_a
        if bos_token:
            tokens = [bos_token] + tokens
        if eos_token:
            tokens += [eos_token]
        segment_ids = [sequence_a_segment_id] * len(tokens)

        # Add sequence separator between sequences
        if tokens_b and sep_token_extra:
            tokens += [sep_token_extra]
            segment_ids += [sequence_a_segment_id]

        # Add special tokens to sequence_b
        if tokens_b:
            if bos_token:
                tokens += [bos_token]
                segment_ids += [sequence_b_segment_id]
            tokens += tokens_b
            segment_ids += [sequence_b_segment_id] * (len(tokens_b))
            if eos_token:
                tokens += [eos_token]
                segment_ids += [sequence_b_segment_id]

        # Add classification token - for BERT models
        if cls_token:
            if cls_token_at_end:
                tokens += [cls_token]
                segment_ids += [cls_token_segment_id]
            else:
                tokens = [cls_token] + tokens
                segment_ids = [cls_token_segment_id] + segment_ids
        input_ids = tokenizer.tokens_to_ids(tokens)

        # The mask has 1 for real tokens and 0 for padding tokens. Only real
        # tokens are attended to.
        input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)

        # Zero-pad up to the sequence length.
        padding_length = max_seq_length - len(input_ids)
        pad_token_id = tokenizer.tokens_to_ids([pad_token])[0]
        if pad_on_left:
            input_ids = ([pad_token_id] * padding_length) + input_ids
            input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
            segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
        else:
            input_ids = input_ids + ([pad_token_id] * padding_length)
            input_mask = input_mask + ([0 if mask_padding_with_zero else 1] * padding_length)
            segment_ids = segment_ids + ([pad_token_segment_id] * padding_length)
        if len(input_ids) != max_seq_length:
            raise ValueError("input_ids must be of length max_seq_length")
        if len(input_mask) != max_seq_length:
            raise ValueError("input_mask must be of length max_seq_length")
        if len(segment_ids) != max_seq_length:
            raise ValueError("segment_ids must be of length max_seq_length")
        if output_mode == "classification":
            label_id = label_map[example.label]
        elif output_mode == "regression":
            label_id = np.float32(example.label)
        else:
            raise KeyError(output_mode)

        if ex_index < 5:
            nemo.logging.info("*** Example ***")
            nemo.logging.info("guid: %s" % (example.guid))
            nemo.logging.info("tokens: %s" % " ".join(list(map(str, tokens))))
            nemo.logging.info("input_ids: %s" % " ".join(list(map(str, input_ids))))
            nemo.logging.info("input_mask: %s" % " ".join(list(map(str, input_mask))))
            nemo.logging.info("segment_ids: %s" % " ".join(list(map(str, segment_ids))))
            nemo.logging.info("label: %s (id = %d)" % (example.label, label_id))

        features.append(
            InputFeatures(input_ids=input_ids, input_mask=input_mask, segment_ids=segment_ids, label_id=label_id)
        )
    return features


def _truncate_seq_pair(tokens_a, tokens_b, max_length):
    """Truncates a sequence pair in place to the maximum length.

     This will always truncate the longer sequence one token at a time.
     This makes more sense than truncating an equal percent
     of tokens from each, since if one sequence is very short then each token
     that's truncated likely contains more information than a longer sequence.
    """
    while True:
        total_length = len(tokens_a) + len(tokens_b)
        if total_length <= max_length:
            break
        if len(tokens_a) > len(tokens_b):
            tokens_a.pop()
        else:
            tokens_b.pop()


class InputFeatures(object):
    """A single set of features of data."""

    def __init__(self, input_ids, input_mask, segment_ids, label_id):
        self.input_ids = input_ids
        self.input_mask = input_mask
        self.segment_ids = segment_ids
        self.label_id = label_id
