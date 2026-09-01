
import torch


available = torch.cuda.is_available()
cuda = torch.version.cuda

print(available)
print(cuda)
