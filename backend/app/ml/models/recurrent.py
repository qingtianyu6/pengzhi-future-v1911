from __future__ import annotations

import torch
from torch import nn


class RecurrentForecaster(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, horizon: int, target_count: int, kind: str = "gru", dropout: float = 0.15) -> None:
        super().__init__()
        recurrent = nn.GRU if kind.lower() == "gru" else nn.LSTM
        self.kind = kind.lower(); self.horizon = horizon; self.target_count = target_count
        self.recurrent = recurrent(input_size=input_size, hidden_size=hidden_size, num_layers=1, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden_size, horizon * target_count)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded, _ = self.recurrent(x)
        return self.output(self.dropout(encoded[:, -1])).reshape(-1, self.horizon, self.target_count)
