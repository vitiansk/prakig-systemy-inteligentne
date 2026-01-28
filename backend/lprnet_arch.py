import torch
import torch.nn as nn

CHARS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
         'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
         'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '-']
CHARS_DICT = {char: i for i, char in enumerate(CHARS)}

class SmallBasicBlock(nn.Module):
    def __init__(self, ch_in, ch_out):
        super(SmallBasicBlock, self).__init__()
        self.block = nn.Sequential(
            nn.Conv2d(ch_in, ch_out // 4, kernel_size=1), nn.ReLU(),
            nn.Conv2d(ch_out // 4, ch_out // 4, kernel_size=(3, 1), padding=(1, 0)), nn.ReLU(),
            nn.Conv2d(ch_out // 4, ch_out // 4, kernel_size=(1, 3), padding=(0, 1)), nn.ReLU(),
            nn.Conv2d(ch_out // 4, ch_out, kernel_size=1)
        )
    def forward(self, x): return self.block(x)

class LPRNet(nn.Module):
    def __init__(self, class_num=37, dropout_rate=0.5):
        super(LPRNet, self).__init__()
        self.class_num = class_num
        self.backbone = nn.Sequential(
            nn.Conv2d(3, 64, 3), nn.BatchNorm2d(64), nn.ReLU(),
            nn.MaxPool3d((1, 3, 3), stride=(1, 1, 1)),
            SmallBasicBlock(64, 128), nn.BatchNorm2d(128), nn.ReLU(),
            nn.MaxPool3d((1, 3, 3), stride=(2, 1, 2)),
            SmallBasicBlock(64, 256), nn.BatchNorm2d(256), nn.ReLU(),
            SmallBasicBlock(256, 256), nn.BatchNorm2d(256), nn.ReLU(),
            nn.MaxPool3d((1, 3, 3), stride=(4, 1, 2)),
            nn.Dropout(dropout_rate),
            nn.Conv2d(64, 256, (1, 4)), nn.BatchNorm2d(256), nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Conv2d(256, class_num, (13, 1)), nn.BatchNorm2d(class_num), nn.ReLU()
        )
        self.container = nn.Conv2d(448 + class_num, class_num, kernel_size=(1, 1))

    def forward(self, x):
        keep_features = []
        for i, layer in enumerate(self.backbone.children()):
            x = layer(x)
            if i in [2, 6, 13, 22]: keep_features.append(x)
        global_context = []
        for i, f in enumerate(keep_features):
            if i in [0, 1]: f = nn.AvgPool2d(5, 5)(f)
            if i == 2: f = nn.AvgPool2d((4, 10), (4, 2))(f)
            f_pow = torch.pow(f, 2)
            f_mean = torch.mean(f_pow)
            global_context.append(torch.div(f, f_mean))
        x = torch.cat(global_context, 1)
        x = self.container(x)
        logits = torch.mean(x, dim=2)
        return logits

def decode_lpr(logits):
    """Dekodowanie CTC (Greedy Decode) - Zgodne z kodem użytkownika"""
    # Logits shape: [Batch, ClassNum, Width]
    # Softmax over ClassNum (dim=1)
    probs = torch.softmax(logits, dim=1)
    # Argmax over ClassNum to get best class for each step
    max_indices = torch.argmax(probs, dim=1)[0].cpu().numpy()
    
    blank_idx = len(CHARS) - 1
    res = []
    prev_idx = -1
    for idx in max_indices:
        if idx != prev_idx and idx != blank_idx:
            res.append(CHARS[idx])
        prev_idx = idx
    return "".join(res)