from __future__ import annotations

import torch
from torch import nn


class SeasonalResidualRNN(nn.Module):
    """Explicit baseline skip connection plus a learned residual."""

    def __init__(self,input_size:int,hidden_size:int,horizon:int,target_count:int,kind:str="gru",dropout:float=.15)->None:
        super().__init__(); recurrent=nn.GRU if kind=="gru" else nn.LSTM; self.kind=kind;self.horizon=horizon;self.target_count=target_count
        self.recurrent=recurrent(input_size,hidden_size,num_layers=1,batch_first=True);self.dropout=nn.Dropout(dropout);self.residual_head=nn.Linear(hidden_size,horizon*target_count)

    def forward(self,x:torch.Tensor,seasonal_base_scaled:torch.Tensor)->torch.Tensor:
        encoded,_=self.recurrent(x); residual=self.residual_head(self.dropout(encoded[:,-1])).reshape(-1,self.horizon,self.target_count)
        return seasonal_base_scaled+residual
