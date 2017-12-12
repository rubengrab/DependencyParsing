import torch
import torch.autograd as autograd
import torch.nn as nn
import numpy as np

import embedding as em

torch.manual_seed(1)

if torch.cuda.is_available():
    floatTensor = torch.cuda.FloatTensor
    longTensor = torch.cuda.LongTensor
else:
    floatTensor = torch.FloatTensor
    longTensor = torch.LongTensor


class BiLSTMTagger(nn.Module):
    def __init__(self, input_size, hidden_dim, num_layers, word_embeddings, pos_embeddings):
        super(BiLSTMTagger, self).__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.word_embeddings = nn.Embedding(word_embeddings.data.shape[0], word_embeddings.data.shape[1])
        self.word_embeddings.weight = nn.Parameter(word_embeddings.data)
        self.word_embeddings.requires_grad = True

        self.pos_embeddings = nn.Embedding(pos_embeddings.data.shape[0], pos_embeddings.data.shape[1])
        self.pos_embeddings.weight = nn.Parameter(pos_embeddings.data)
        self.pos_embeddings.requires_grad = True

        self.bilstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_dim // 2,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True
        )

        self.num_directions = 2 if self.bilstm.bidirectional else 1

        self.hidden = self.init_hidden()

        # One linear layer Wx + b, input dim 100 output dim 100
        self.mlp_head1 = nn.Linear(input_size, input_size)
        self.mlp_head2 = nn.Linear(input_size, input_size)

        # One linear layer Wx + b, input dim 100 output dim 100
        self.mlp_dependent1 = nn.Linear(input_size, input_size)
        self.mlp_dependent2 = nn.Linear(input_size, input_size)

        # activation function  h(Wx + b)
        self.ReLU = nn.ReLU()

        # One bi-linear layer x1∗W1∗x2+b, input1 dim 100,input2 dim 100, output dim 1
        self.bi_linear = nn.Bilinear(input_size, input_size, 1)

        if torch.cuda.is_available():
            self.cuda()
        else:
            self.cpu()

    def init_hidden(self):
        # Before we've done anything, we don't have any hidden state.
        # Refer to the PyTorch documentation to see exactly why they have this dimensionality.
        # The axes semantics are (num_layers*num_directions, mini-batch_size, hidden_dim)
        return (autograd.Variable(torch.zeros(self.num_layers * self.num_directions, 1, self.hidden_dim // 2)).type(floatTensor),
                autograd.Variable(torch.zeros(self.num_layers * self.num_directions, 1, self.hidden_dim // 2)).type(floatTensor))

    def forward(self, sentence_word_indices, sentence_pos_indices):
        # get embeddings for sentence
        embedded_sentence = torch.cat((self.word_embeddings(sentence_word_indices), self.pos_embeddings(sentence_pos_indices)), 1)
        inputs = embedded_sentence.view(len(embedded_sentence), 1, -1)

        # pass through the biLstm layer
        lstm_out, self.hidden = self.bilstm(inputs, self.hidden)

        # TODO: we could use a technique called 'tiling', to have matrix multiplications instead of 'for in for'
        # do further processing in MLP
        # for each pair v_i, v_j, go with v_1 through mlp_head and with v_j to mlp_dependent
        matrix = []
        for v_i in lstm_out:
            matrix_row = []
            for v_j in lstm_out:
                v_i_head = self.ReLU(self.mlp_head2(self.ReLU(self.mlp_head1(v_i))))
                v_j_dependent = self.ReLU(self.mlp_dependent2(self.ReLU(self.mlp_dependent1(v_j))))

                # for each pair, of v_i_head and v_j_dependent go through bi_linear, so that we have a score
                score = self.bi_linear(v_i_head, v_j_dependent)

                # append to matrix_row the score
                matrix_row.append(score)

            matrix_row = torch.cat(matrix_row, 1)

            # append to matrix  the rows
            matrix.append(matrix_row)

        matrix = torch.cat(matrix, 0)  # TODO: we return the matrix as it is, because torch.CrossEntropyLoss will apply softmax on it.

        return matrix


def prepare_sequence(sequence, element2index):
    """
    :param sequence: sequence of elements
    :param element2index: dictionary to map elements to index
    :return: autograd.Variable(torch.LongTensor(X)), where "X" is the sequence of indexes.
    """
    indexes = [element2index[element] for element in sequence]
    tensor = longTensor(indexes)
    return autograd.Variable(tensor)


if __name__ == '__main__':
    word_embeddings = autograd.Variable(torch.from_numpy(np.array(em.word_embeddings()).astype(np.float)).float())
    pos_embeddings = autograd.Variable(torch.from_numpy(np.array(em.tag_embeddings()).astype(np.float)).float())

    model = BiLSTMTagger(input_size=100, hidden_dim=100, num_layers=2, word_embeddings=word_embeddings,
                         pos_embeddings=pos_embeddings)

    loss_function = nn.CrossEntropyLoss()

    parameters = filter(lambda p: p.requires_grad, model.parameters())
    optimizer = torch.optim.SGD(parameters, lr=0.1)

    conllu_sentences = em.en_train_sentences()

    count = 0
    for epoch in range(1):
        counter = 0
        for conllu_sentence in conllu_sentences:
            print(count)
            count += 1

            sentence = conllu_sentence.get_word_list()
            tags = conllu_sentence.get_pos_list()

            # Step 1. Remember that PyTorch accumulates gradients.
            # We need to clear them out before each instance
            model.zero_grad()

            # Also, we need to clear out the hidden state of the LSTM,
            # detaching it from its history on the last instance.
            model.hidden = model.init_hidden()

            # Step 2. Get our inputs ready for the network, that is, turn them into
            # Variables of word indices.
            sentence_in = prepare_sequence(sentence, em.w2i)
            post_tags_in = prepare_sequence(tags, em.t2i)

            # Step 3. Run our forward pass.
            arc_scores = model(sentence_in, post_tags_in)

            # Step 4. Compute the loss, gradients, and update the parameters by calling optimizer.step()
            targets = autograd.Variable(torch.from_numpy(np.array(conllu_sentence.get_head_representation()).astype(np.float))).type(float)
            loss = loss_function(arc_scores.permute(1, 0), targets)  # TODO: check to see how exactly to send the data to loss function(i.e. 'permute' or 'no permute'??)
            loss.backward()
            optimizer.step()