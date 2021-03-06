# -*- coding: utf-8 -*-
"""edgar_poe_text_generation_v1.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1dbwskZmum_hZnroK4j-G-fa0Ffsp7rCW

# Preprocessing
"""

import numpy as np
import pandas as pd

data=pd.read_csv('drive/My Drive/edgar_poe.zip')#loading dataset
data=data.sample(frac=1)#shuffling data

data.drop(['title','wikipedia_title','publication_date','first_published_in','notes','normalized_date'],axis=1,inplace=True)

#Counting how often each genre is met in the dataset
genre_count={}

for i in range(len(data['classification'])):
  token_to_id=data['classification'][i].split(',')
  for j in range(len(token_to_id)):
    if token_to_id[j] not in genre_count:
      genre_count[token_to_id[j]] = 1
    else: genre_count[token_to_id[j]]+=1

for i in range(len(data)):
  if len(data['classification'][i].split(',')) > 1:
    data['classification'][i]=list(genre_count.keys())[list(genre_count.values()).index(np.min([genre_count[j] for j in data['classification'][i].split(',')]))]

data

#figuring out genre tokens
token_to_id={
    '':0
}
a=1

for i in range(len(data['classification'])):
  if data['classification'][i] not in token_to_id:
    token_to_id[data['classification'][i]] = a
    a+=1

#remove all punctuation marks function
def remove_punctuation_marks(string):
  string_list=string.split(' ')
  for i in range(len(string_list)):
    for j in range(len(string_list[i])):
      if string_list[i][j] in ',.@#$%"“^&*()?/*-+!"№;”%:<>=`~[]{}':
        string=string.replace(string_list[i][j],'')
  string_list=string.lower().split(' ')
  while '' in string_list:
    string_list.remove('')
  return string_list

data['text']=data['text'].apply(remove_punctuation_marks)

#figuring out words tokens

a=len(token_to_id)

for i in range(len(data['text'])):
  for j in range(len(data['text'][i])):
    if data['text'][i][j] not in token_to_id:
      token_to_id[data['text'][i][j]]=a
      a+=1

id_to_token={i : char for char, i in token_to_id.items()}#making id -> token dictionary

#function that makes vector out of given string using token_to_id dictionary
def string_to_vector(string,maxlen):
  vect=[]
  for i in range(len(string)):
    vect.append(token_to_id[string[i]])
  while len(vect) != maxlen:
    vect.append(token_to_id[''])
  return vect

def splitter(vector,splitted_size):
  #because of given texts are too long we are making "splitted_size" different batches from all given poems
  splitted_data = []
  vector = vector[0 : (len(vector)-(len(vector) % splitted_size))]
  for i in range(splitted_size):
    splitted_data.append(vector[i * int(len(vector)/splitted_size) : (i+1) * int(len(vector)/splitted_size)])
  return splitted_data

data['text_vectorized']=data['text'].apply(string_to_vector,maxlen=np.max(list(map(len,data['text']))))#vectorizing
data['text_vectorized']=data['text_vectorized'].apply(splitter, splitted_size=10)#splitting texts into batches

#for each batch of every single text we are adding a genre id to its begging so rnn could better remember the sequences to each genre
for i in range(len(data['text_vectorized'])):
  for j in range(len(data['text_vectorized'][i])):
    data['text_vectorized'][i][j]=[token_to_id[data['classification'][i]]]+data['text_vectorized'][i][j]

data.drop(['text','classification'],axis=1,inplace=True)

"""# Teaching RNN on given texts"""

import torch, torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from time import time
from IPython.display import clear_output
from numpy.random import choice
import matplotlib.pyplot as plt

#rnn architecture performed by Svyatoslav O.
class CharRNNLoop(nn.Module):
    def __init__(self, num_tokens=len(token_to_id), emb_size=16, rnn_num_units=64):
        super(self.__class__, self).__init__()
        self.emb = nn.Embedding(num_tokens, emb_size)
        self.rnn = nn.RNN(emb_size, rnn_num_units, batch_first=True)
        self.hid_to_logits = nn.Linear(rnn_num_units, num_tokens)
        
    def forward(self, x, hidden_state=None):
        assert isinstance(x, Variable) and isinstance(x.data, torch.LongTensor)
        if hidden_state is not None:
            h_seq, new_hidden = self.rnn(self.emb(x), hidden_state)
        else:
            h_seq, new_hidden = self.rnn(self.emb(x))
        next_logits = self.hid_to_logits(h_seq)
        next_logp = F.log_softmax(next_logits, dim=-1)
        return next_logp, new_hidden

model=CharRNNLoop()
opt=torch.optim.Adam(model.parameters())

#doing one single forward pass
batch_ix = choice(data['text_vectorized'][2][2],1)
batch_ix = torch.LongTensor(batch_ix)

logp_seq, _ = model(np.reshape(batch_ix,(batch_ix.shape[0],1)))

loss = F.nll_loss(logp_seq[:, 1:].contiguous().view(-1, len(token_to_id)), 
                  batch_ix[ :-1].contiguous().view(-1))
loss.backward()

#fitting model
history = []
time0=time()

for i in range(70):
    batch_ix = torch.tensor(data['text_vectorized'][i], dtype=torch.int64)
    
    logp_seq, _ = model(batch_ix)

    predictions_logp = logp_seq[:, :-1]
    actual_next_tokens = batch_ix[:, 1:]
    loss = -torch.mean(torch.gather(predictions_logp, dim=2, index=actual_next_tokens[:,:,None]))

    loss.backward()
    opt.step()
    opt.zero_grad()
    
    history.append(loss.data.numpy())
    
    if (i + 1) % 7 == 0:
        clear_output(True)
        plt.plot(history, label='loss')
        plt.legend()
        plt.show()

print('{} minutes have passed'.format((time()-time0)/60))

#saving model
torch.save(model.state_dict(), 'rnn_path')

model=CharRNNLoop()
model.load_state_dict(torch.load("drive/My Drive/rnn_path")

"""# Generating texts using RNN"""

def generate_sample(char_rnn, seed_phrase=' hello ', max_length=100, temperature=1.0):
    '''
    The function generates text given a phrase of length at least SEQ_LENGTH.
    :param seed_phrase: prefix characters. The RNN is asked to continue the phrase
    :param max_length: maximum output length, including seed_phrase
    :param temperature: coefficient for sampling.  higher temperature produces more chaotic outputs,
                        smaller temperature converges to the single most likely output
    '''
    
    x_sequence = [token_to_id[token] for token in seed_phrase.split(' ')]
    x_sequence = torch.tensor([x_sequence], dtype=torch.int64)

    hidden_s = None
    for i in range(len(seed_phrase.split(' '))):
        _, hidden_s = char_rnn.forward(np.reshape(x_sequence[:,-1],(1,1)),hidden_s)

    for _ in range(max_length - len(seed_phrase.split(' '))):
        logp_next, hidden_s = char_rnn.forward(np.reshape(x_sequence[:,-1],(1,1)), hidden_s)
        p_next = F.softmax(logp_next / temperature, dim=-1).data.numpy()[0]
        next_ix = np.random.choice(len(token_to_id), p=p_next[0])
        next_ix = torch.tensor([[[list(id_to_token.keys())[next_ix]]]], dtype=torch.int64)
        x_sequence = torch.cat([np.reshape(x_sequence,(x_sequence.shape[0],x_sequence.shape[1],1)), next_ix], dim=1)
    return ' '.join([str(id_to_token[i]) for i in np.reshape(x_sequence,(x_sequence.shape[1])).tolist()])

for i in [0.1,0.5,0.7,1,1.3,1.5,2]:
  print(generate_sample(model, seed_phrase='Horror', max_length = 30, temperature=i))
  print()

token_to_id

